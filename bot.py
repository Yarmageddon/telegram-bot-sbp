"""
Главный файл бота — все хэндлеры, FSM, логика
Исправлено:
  - Звёзды: отображаются цифрами 1★ 2★ 3★ 4★ 5★ (Telegram обрезает повторяющиеся emoji в кнопках)
  - AI: подключён через OPENAI_API_KEY (env), fallback на заглушку если ключ не задан
  - OCR: исправлен bot.download() вместо устаревшего bot.download_file()
  - PDF: исправлен bot.download() + FSInputFile импортирован наверху
  - Двойные декораторы: разделены на отдельные хэндлеры (aiogram3 не поддерживает стекинг message+callback)
"""
import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, BotCommand, FSInputFile

from config import settings
from models import init_db
from database import (
    get_or_create_user, get_active_subscription, create_subscription,
    create_payment, complete_payment, get_pending_payments, get_user_payments,
    start_trial, get_trial, create_review, get_rating_stats,
    create_ticket, get_open_tickets, answer_ticket,
    create_news, get_all_users, get_bot_stats, get_user_by_ref_code, apply_referral,
)
from keyboards import (
    main_menu, back_menu, subscription_plans, payment_confirm,
    trial_keyboard, docs_keyboard, ai_keyboard, ai_templates_keyboard,
    account_keyboard, referral_keyboard, review_rating_keyboard,
    support_keyboard, admin_keyboard,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

PLANS = {
    "basic":    {"name": "Базовый",  "price": settings.PRICE_BASIC,    "days": 30},
    "pro":      {"name": "Про",      "price": settings.PRICE_PRO,      "days": 30},
    "business": {"name": "Бизнес",   "price": settings.PRICE_BUSINESS, "days": 30},
}


# ── FSM States ────────────────────────────────────────────────────────────────

class ReviewStates(StatesGroup):
    waiting_rating = State()
    waiting_text   = State()

class SupportStates(StatesGroup):
    waiting_message = State()

class AIStates(StatesGroup):
    waiting_question = State()

class DocStates(StatesGroup):
    waiting_pdf   = State()
    waiting_text  = State()
    waiting_photo = State()

class AdminStates(StatesGroup):
    broadcast_text    = State()
    answer_ticket_text = State()


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids_list


def subscription_status_text(user_id: int) -> str:
    sub   = get_active_subscription(user_id)
    trial = get_trial(user_id)
    if sub:
        days = (sub.expires_at - datetime.now()).days
        return f"💎 <b>Подписка:</b> {sub.plan.capitalize()} · ещё {days} дн. (до {sub.expires_at.strftime('%d.%m.%Y')})"
    if trial and trial.used and trial.expires_at > datetime.now():
        days = (trial.expires_at - datetime.now()).days
        return f"🎁 <b>Триал:</b> ещё {days} дн. (до {trial.expires_at.strftime('%d.%m.%Y')})"
    return "❌ <b>Подписка:</b> не активна"


def has_access(user_id: int) -> bool:
    if get_active_subscription(user_id):
        return True
    trial = get_trial(user_id)
    return bool(trial and trial.used and trial.expires_at > datetime.now())


# ── AI helper ─────────────────────────────────────────────────────────────────

async def get_ai_response(question: str, template: str = None) -> str:
    """
    Если задан OPENAI_API_KEY — реальный вызов GPT-4o-mini.
    Иначе — качественная заглушка с шаблонными ответами.
    """
    api_key = os.getenv("OPENAI_API_KEY", "")

    if api_key:
        try:
            import httpx
            system_prompts = {
                "tpl_email":   "Ты помощник по деловой переписке. Напиши профессиональное письмо на русском языке по запросу пользователя.",
                "tpl_bizplan": "Ты бизнес-консультант. Составь краткий структурированный бизнес-план по описанию пользователя.",
                "tpl_ad":      "Ты копирайтер. Напиши продающий рекламный текст по запросу пользователя.",
                "tpl_cv":      "Ты HR-специалист. Помоги составить резюме по данным пользователя.",
            }
            system = system_prompts.get(template, "Ты полезный AI-ассистент. Отвечай на русском языке чётко и по делу.")

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user",   "content": question},
                        ],
                        "max_tokens": 800,
                    },
                )
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            return f"⚠️ Ошибка AI-сервиса: {e}\n\nПовторите запрос позже."

    # ── Заглушка (нет API-ключа) ──────────────────────────────────────────────
    q = question.lower()
    if template == "tpl_email":
        return (
            f"Уважаемый получатель,\n\n"
            f"Пишу вам по вопросу: {question}\n\n"
            f"Прошу рассмотреть данное обращение и дать ответ в удобное для вас время.\n\n"
            f"С уважением"
        )
    if template == "tpl_bizplan":
        return (
            f"📊 <b>Бизнес-план: {question[:60]}</b>\n\n"
            f"<b>1. Концепция:</b> {question}\n"
            f"<b>2. Целевая аудитория:</b> [опишите ЦА]\n"
            f"<b>3. Монетизация:</b> [укажите модель дохода]\n"
            f"<b>4. Конкуренты:</b> [анализ рынка]\n"
            f"<b>5. Финансовая модель:</b> [затраты / выручка / ROI]\n\n"
            f"💡 Для детального плана подключите OPENAI_API_KEY в настройках бота."
        )
    if template == "tpl_ad":
        return (
            f"🔥 <b>Рекламный текст</b>\n\n"
            f"Устали от {question}? Мы знаем решение!\n\n"
            f"✅ Быстро · ✅ Надёжно · ✅ Выгодно\n\n"
            f"👉 Успей воспользоваться предложением — количество мест ограничено!\n\n"
            f"💡 Для уникального текста подключите OPENAI_API_KEY."
        )
    if template == "tpl_cv":
        return (
            f"📄 <b>Резюме</b>\n\n"
            f"<b>Профессия/Специализация:</b> {question}\n\n"
            f"<b>Опыт работы:</b>\n• [Компания, должность, период]\n\n"
            f"<b>Образование:</b>\n• [Вуз, специальность, год]\n\n"
            f"<b>Ключевые навыки:</b>\n• [навык 1] · [навык 2] · [навык 3]\n\n"
            f"💡 Для персонального резюме подключите OPENAI_API_KEY."
        )
    if any(w in q for w in ["привет", "hello", "hi", "здравствуй"]):
        return "Привет! Чем могу помочь? Задай любой вопрос или выбери шаблон."
    if any(w in q for w in ["цена", "стоимость", "тариф", "сколько стоит"]):
        return (
            "💎 <b>Тарифы:</b>\n\n"
            "🟢 Базовый — 299₽/мес\n"
            "🔵 Про — 799₽/мес\n"
            "🟣 Бизнес — 1999₽/мес\n\n"
            "🎁 Пробный период — 7 дней бесплатно!"
        )
    return (
        f"🤖 <b>Демо-режим AI</b>\n\n"
        f"Вопрос: «{question[:120]}»\n\n"
        f"Для полноценного AI-ответа администратору нужно добавить "
        f"переменную <code>OPENAI_API_KEY</code> в настройки Railway.\n\n"
        f"Пока доступны шаблоны: email, бизнес-план, рекламный текст, резюме."
    )


# ── /start ────────────────────────────────────────────────────────────────────

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    args = message.text.split()
    ref_code = args[1] if len(args) > 1 else None

    user = get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name,
    )

    if ref_code and ref_code != user.referral_code:
        referrer = get_user_by_ref_code(ref_code)
        if referrer and referrer.id != user.id:
            apply_referral(user.id, referrer.id)
            create_subscription(referrer.id, "referral_bonus", settings.REFERRAL_BONUS_DAYS)
            try:
                await bot.send_message(
                    referrer.telegram_id,
                    f"🎉 По вашей ссылке зарегистрировался новый пользователь!\n"
                    f"Вы получили <b>{settings.REFERRAL_BONUS_DAYS} дней</b> подписки! 🎁",
                    parse_mode="HTML",
                )
            except Exception:
                pass

    name = message.from_user.first_name or "друг"
    await message.answer(
        f"👋 <b>Привет, {name}!</b>\n\n"
        "Добро пожаловать! Этот бот поможет тебе:\n\n"
        "🤖 <b>AI-ассистент</b> — ответы на любые вопросы\n"
        "📄 <b>Документы</b> — конвертация PDF, OCR\n"
        "💎 <b>Подписки</b> — базовая, про, бизнес\n"
        "🎁 <b>Триал</b> — 7 дней бесплатно\n"
        "👥 <b>Рефералы</b> — приглашай и получай бонусы\n\n"
        "Выбери раздел:",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# ── /help ─────────────────────────────────────────────────────────────────────

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📚 <b>Команды бота:</b>\n\n"
        "/start — главное меню\n"
        "/account — личный кабинет\n"
        "/subscribe — подписка\n"
        "/trial — активировать триал\n"
        "/support — поддержка\n"
        "/help — эта справка\n\n"
        "💡 Используй кнопки меню для быстрого доступа!",
        parse_mode="HTML",
        reply_markup=back_menu(),
    )


# ── Главное меню ──────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "back_main")
async def cb_back_main(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text(
        "🏠 <b>Главное меню</b>\n\nВыбери раздел:",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# ── Подписка (команда) ────────────────────────────────────────────────────────

@dp.message(Command("subscribe"))
async def cmd_subscribe(message: Message, state: FSMContext):
    await state.clear()
    user = get_or_create_user(message.from_user.id)
    await message.answer(
        _subscription_text(user.id),
        parse_mode="HTML",
        reply_markup=subscription_plans(),
    )


@dp.callback_query(F.data == "menu_sub")
async def cb_subscribe(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_or_create_user(cb.from_user.id)
    await cb.message.edit_text(
        _subscription_text(user.id),
        parse_mode="HTML",
        reply_markup=subscription_plans(),
    )


def _subscription_text(user_id: int) -> str:
    return (
        f"💎 <b>Подписка</b>\n\n"
        f"{subscription_status_text(user_id)}\n\n"
        "Выбери тарифный план:\n\n"
        "🟢 <b>Базовый — 299₽/мес</b>\n"
        "• AI-ассистент (50 запросов/день)\n"
        "• Конвертация документов (10 шт/день)\n"
        "• OCR распознавание\n\n"
        "🔵 <b>Про — 799₽/мес</b>\n"
        "• AI-ассистент (безлимит)\n"
        "• Конвертация документов (50 шт/день)\n"
        "• OCR + приоритетная поддержка\n\n"
        "🟣 <b>Бизнес — 1999₽/мес</b>\n"
        "• Всё из Про\n"
        "• Командный доступ\n"
        "• Персональный менеджер\n"
    )


@dp.callback_query(F.data.startswith("plan_"))
async def select_plan(cb: CallbackQuery, state: FSMContext):
    plan_key = cb.data.replace("plan_", "")
    plan = PLANS.get(plan_key)
    if not plan:
        await cb.answer("Неизвестный план", show_alert=True)
        return

    user = get_or_create_user(cb.from_user.id)
    payment = create_payment(user.id, plan["price"], plan_key)
    await state.update_data(plan=plan_key, payment_id=payment.id)

    for admin_id in settings.admin_ids_list:
        try:
            await bot.send_message(
                admin_id,
                f"💰 <b>Новый платёж #{payment.id}</b>\n"
                f"Пользователь: @{cb.from_user.username or '-'} (ID: {cb.from_user.id})\n"
                f"Тариф: {plan['name']} · {plan['price']} ₽\n\n"
                f"Подтвердить: /confirm_{payment.id}",
                parse_mode="HTML",
            )
        except Exception:
            pass

    await cb.message.edit_text(
        f"💳 <b>Оплата: {plan['name']}</b>\n\n"
        f"Сумма: <b>{plan['price']} ₽</b>\n\n"
        f"Переведи на реквизиты:\n"
        f"💳 Карта: <code>{settings.PAYMENT_CARD}</code>\n"
        f"📱 СБП: <code>{settings.PAYMENT_PHONE}</code>\n\n"
        f"В комментарии укажи свой ID: <code>{cb.from_user.id}</code>\n\n"
        f"После оплаты нажми <b>«✅ Я оплатил»</b>.",
        parse_mode="HTML",
        reply_markup=payment_confirm(plan_key, plan["price"]),
    )


@dp.callback_query(F.data.startswith("paid_"))
async def payment_by_user(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text(
        "⏳ <b>Платёж отправлен на проверку!</b>\n\n"
        "Администратор проверит оплату и активирует подписку.\n"
        "Вы получите уведомление в этом чате.",
        parse_mode="HTML",
        reply_markup=back_menu(),
    )


@dp.message(Command(commands=["confirm"]))
async def admin_confirm_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split("_")
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Формат: /confirm_<payment_id>")
        return
    await _do_confirm_payment(int(parts[1]), message)


async def _do_confirm_payment(payment_id: int, message: Message):
    from models import SessionLocal, Payment as PM, User as UM
    db = SessionLocal()
    try:
        p = db.query(PM).filter(PM.id == payment_id).first()
        if not p:
            await message.answer(f"❌ Платёж #{payment_id} не найден")
            return
        if p.status == "completed":
            await message.answer(f"✅ Платёж #{payment_id} уже подтверждён")
            return
        plan = PLANS.get(p.plan)
        if not plan:
            await message.answer(f"❌ Неизвестный тариф: {p.plan}")
            return
        complete_payment(payment_id)
        create_subscription(p.user_id, p.plan, plan["days"])
        user = db.query(UM).filter(UM.id == p.user_id).first()
        if user:
            try:
                await bot.send_message(
                    user.telegram_id,
                    f"🎉 <b>Подписка активирована!</b>\n\n"
                    f"Тариф: <b>{plan['name']}</b> · {plan['days']} дней\n\n"
                    f"Используй /start для доступа ко всем функциям.",
                    parse_mode="HTML",
                )
            except Exception:
                pass
        await message.answer(f"✅ Платёж #{payment_id} подтверждён, подписка активирована!")
    finally:
        db.close()


# ── Триал (команда) ───────────────────────────────────────────────────────────

@dp.message(Command("trial"))
async def cmd_trial(message: Message, state: FSMContext):
    await state.clear()
    user  = get_or_create_user(message.from_user.id)
    trial = get_trial(user.id)
    text, kb = _trial_text_kb(trial)
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@dp.callback_query(F.data == "menu_trial")
async def cb_trial(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    user  = get_or_create_user(cb.from_user.id)
    trial = get_trial(user.id)
    text, kb = _trial_text_kb(trial)
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


def _trial_text_kb(trial):
    if trial and trial.used:
        if trial.expires_at > datetime.now():
            days = (trial.expires_at - datetime.now()).days
            return (
                f"🎁 <b>Триал активен</b>\n\nОсталось: <b>{days} дн.</b>\n"
                f"Истекает: {trial.expires_at.strftime('%d.%m.%Y')}",
                back_menu(),
            )
        return (
            "❌ <b>Триал уже использован</b>\n\nОформи подписку для продолжения.",
            subscription_plans(),
        )
    return (
        "🎁 <b>Пробный период — 7 дней бесплатно!</b>\n\n"
        "Полный доступ ко всем функциям:\n"
        "• AI-ассистент\n• Конвертация документов\n• OCR распознавание\n\n"
        "Активируй один раз, без привязки карты!",
        trial_keyboard(),
    )


@dp.callback_query(F.data == "activate_trial")
async def activate_trial(cb: CallbackQuery):
    user   = get_or_create_user(cb.from_user.id)
    result = start_trial(user.id, days=7)
    if result["success"]:
        await cb.message.edit_text(
            "🎉 <b>Триал активирован на 7 дней!</b>\n\nПолный доступ ��ткрыт. Используй /start.",
            parse_mode="HTML",
            reply_markup=back_menu(),
        )
    else:
        await cb.message.edit_text(
            f"❌ {result['message']}\n\nОформи подписку для продолжения.",
            parse_mode="HTML",
            reply_markup=subscription_plans(),
        )


# ── AI-Ассистент ──────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_ai")
async def cb_ai(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    ai_available = bool(os.getenv("OPENAI_API_KEY"))
    status = "🟢 подключён" if ai_available else "🟡 демо-режим (добавь OPENAI_API_KEY)"
    await cb.message.edit_text(
        f"🤖 <b>AI-Ассистент</b> — {status}\n\n"
        "Задай любой вопрос или выбери готовый шаблон:\n\n"
        "• Email и деловая переписка\n"
        "• Бизнес-план\n"
        "• Рекламный текст\n"
        "• Резюме\n"
        "• Любой свободный вопрос",
        parse_mode="HTML",
        reply_markup=ai_keyboard(),
    )


@dp.callback_query(F.data == "ai_ask")
async def ai_ask(cb: CallbackQuery, state: FSMContext):
    user = get_or_create_user(cb.from_user.id)
    if not has_access(user.id):
        await cb.message.edit_text(
            "🔒 <b>Требуется подписка</b>\n\nАктивируй триал на 7 дней бесплатно!",
            parse_mode="HTML",
            reply_markup=trial_keyboard(),
        )
        return
    await state.set_state(AIStates.waiting_question)
    await cb.message.edit_text(
        "🤖 <b>AI-Ассистент</b>\n\nНапиши свой вопрос:",
        parse_mode="HTML",
        reply_markup=back_menu(),
    )


@dp.callback_query(F.data == "ai_templates")
async def ai_templates(cb: CallbackQuery):
    await cb.message.edit_text(
        "📋 <b>Шаблоны запросов</b>\n\nВыбери шаблон:",
        parse_mode="HTML",
        reply_markup=ai_templates_keyboard(),
    )


@dp.callback_query(F.data.startswith("tpl_"))
async def ai_template_selected(cb: CallbackQuery, state: FSMContext):
    user = get_or_create_user(cb.from_user.id)
    if not has_access(user.id):
        await cb.message.edit_text(
            "🔒 <b>Требуется подписка</b>\n\nАктивируй триал на 7 дней бесплатно!",
            parse_mode="HTML",
            reply_markup=trial_keyboard(),
        )
        return
    prompts = {
        "tpl_email":   "📧 Опиши кому и по какому поводу написать письмо:",
        "tpl_bizplan": "📊 Опиши свою бизнес-идею в нескольких словах:",
        "tpl_ad":      "📣 Что рекламируем? Для кого? Желаемый тон:",
        "tpl_cv":      "📝 Укажи профессию, опыт и ключевые навыки:",
    }
    await state.set_state(AIStates.waiting_question)
    await state.update_data(template=cb.data)
    await cb.message.edit_text(
        prompts.get(cb.data, "Напиши запрос:"),
        parse_mode="HTML",
        reply_markup=back_menu(),
    )


@dp.message(AIStates.waiting_question)
async def process_ai_question(message: Message, state: FSMContext):
    data     = await state.get_data()
    template = data.get("template")
    await state.clear()

    thinking_msg = await message.answer("⏳ Обрабатываю запрос...")
    response = await get_ai_response(message.text.strip(), template)
    await thinking_msg.delete()
    await message.answer(
        f"🤖 <b>AI-ответ:</b>\n\n{response}",
        parse_mode="HTML",
        reply_markup=ai_keyboard(),
    )


# ── Документы ─────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_docs")
async def cb_docs(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_or_create_user(cb.from_user.id)
    if not has_access(user.id):
        await cb.message.edit_text(
            "🔒 <b>Требуется подписка</b>\n\nАктивируй триал на 7 дней бесплатно!",
            parse_mode="HTML",
            reply_markup=trial_keyboard(),
        )
        return
    await cb.message.edit_text(
        "📄 <b>Работа с документами</b>\n\nВыбери действие:",
        parse_mode="HTML",
        reply_markup=docs_keyboard(),
    )


@dp.callback_query(F.data == "doc_pdf2txt")
async def doc_pdf_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(DocStates.waiting_pdf)
    await cb.message.edit_text(
        "📄 <b>PDF → Текст</b>\n\nОтправь PDF-файл:",
        parse_mode="HTML",
        reply_markup=back_menu(),
    )


@dp.callback_query(F.data == "doc_txt2pdf")
async def doc_txt_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(DocStates.waiting_text)
    await cb.message.edit_text(
        "📝 <b>Текст → PDF</b>\n\nОтправь текст для конвертации:",
        parse_mode="HTML",
        reply_markup=back_menu(),
    )


@dp.callback_query(F.data == "doc_ocr")
async def doc_ocr_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(DocStates.waiting_photo)
    await cb.message.edit_text(
        "🔍 <b>OCR — распознавание текста с фото</b>\n\nОтправь фотографию или изображение:",
        parse_mode="HTML",
        reply_markup=back_menu(),
    )


@dp.message(DocStates.waiting_pdf, F.document)
async def handle_pdf(message: Message, state: FSMContext):
    doc = message.document
    if not doc.file_name.lower().endswith(".pdf"):
        await message.answer("❌ Нужен PDF-файл. Попробуй ещё раз.", reply_markup=back_menu())
        return
    await message.answer("⏳ Обрабатываю PDF...")
    try:
        tmp_path = f"/tmp/{uuid.uuid4().hex}.pdf"
        # aiogram3: bot.download принимает file_id и destination
        await bot.download(doc.file_id, destination=tmp_path)

        from documents import convert_pdf_to_text
        ok, msg, text = convert_pdf_to_text(tmp_path)
        os.remove(tmp_path)

        if ok:
            chunks = [text[i:i + 4000] for i in range(0, min(len(text), 12000), 4000)]
            for chunk in chunks:
                await message.answer(
                    f"📄 <b>Текст из PDF:</b>\n\n<code>{chunk}</code>",
                    parse_mode="HTML",
                )
        else:
            await message.answer(f"❌ {msg}", reply_markup=back_menu())
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=back_menu())
    await state.clear()


@dp.message(DocStates.waiting_text)
async def handle_text_to_pdf(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("❌ Нужен текст. Попробуй ещё раз.")
        return
    await message.answer("⏳ Создаю PDF...")
    try:
        from documents import convert_text_to_pdf
        ok, msg, path = convert_text_to_pdf(message.text)
        if ok:
            await message.answer_document(FSInputFile(path), caption="✅ PDF готов!")
            os.remove(path)
        else:
            await message.answer(f"❌ {msg}", reply_markup=back_menu())
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=back_menu())
    await state.clear()


@dp.message(DocStates.waiting_photo, F.photo | F.document)
async def handle_ocr(message: Message, state: FSMContext):
    await message.answer("⏳ Распознаю текст...")
    try:
        if message.photo:
            file_id = message.photo[-1].file_id
            ext = "jpg"
        else:
            ext = message.document.file_name.rsplit(".", 1)[-1] if "." in message.document.file_name else "jpg"
            file_id = message.document.file_id

        tmp_path = f"/tmp/{uuid.uuid4().hex}.{ext}"
        # aiogram3: bot.download принимает file_id и destination
        await bot.download(file_id, destination=tmp_path)

        from documents import ocr_from_image
        ok, msg, text = ocr_from_image(tmp_path)
        os.remove(tmp_path)

        if ok:
            await message.answer(
                f"🔍 <b>Распознанный текст:</b>\n\n<code>{text[:4000]}</code>",
                parse_mode="HTML",
            )
        else:
            await message.answer(f"❌ {msg}", reply_markup=back_menu())
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=back_menu())
    await state.clear()


# ── Личный кабинет ────────────────────────────────────────────────────────────

@dp.message(Command("account"))
async def cmd_account(message: Message, state: FSMContext):
    await state.clear()
    await _show_account(message.from_user.id, message)


@dp.callback_query(F.data == "menu_account")
async def cb_account(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await _show_account(cb.from_user.id, cb)


async def _show_account(telegram_id: int, target):
    user     = get_or_create_user(telegram_id)
    payments = get_user_payments(user.id)
    total    = sum(p.amount for p in payments if p.status == "completed")
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user.referral_code}"

    text = (
        f"👤 <b>Личный кабинет</b>\n\n"
        f"<b>Имя:</b> {user.first_name or '—'}\n"
        f"<b>Username:</b> @{user.username or '—'}\n"
        f"<b>ID:</b> <code>{user.telegram_id}</code>\n"
        f"<b>Регистрация:</b> {user.created_at.strftime('%d.%m.%Y')}\n\n"
        f"{subscription_status_text(user.id)}\n\n"
        f"<b>Реферальная ссылка:</b>\n<code>{ref_link}</code>\n\n"
        f"<b>Всего оплачено:</b> {total:.0f} ₽"
    )
    if isinstance(target, Message):
        await target.answer(text, parse_mode="HTML", reply_markup=account_keyboard())
    else:
        await target.message.edit_text(text, parse_mode="HTML", reply_markup=account_keyboard())


@dp.callback_query(F.data == "acc_payments")
async def cb_payments(cb: CallbackQuery):
    user     = get_or_create_user(cb.from_user.id)
    payments = get_user_payments(user.id)
    if not payments:
        text = "💳 <b>История платежей</b>\n\nПлатежей пока нет."
    else:
        lines = ["💳 <b>История платежей:</b>\n"]
        for p in payments:
            emoji = "✅" if p.status == "completed" else "⏳"
            lines.append(f"{emoji} {p.amount:.0f} ₽ · {p.plan or '—'} · {p.created_at.strftime('%d.%m.%Y')}")
        text = "\n".join(lines)
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=account_keyboard())


@dp.callback_query(F.data == "acc_stats")
async def cb_stats(cb: CallbackQuery):
    user  = get_or_create_user(cb.from_user.id)
    stats = get_rating_stats()
    await cb.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"Рейтинг бота: ⭐ {stats['average']} ({stats['total']} отзывов)\n"
        f"Твой аккаунт с: {user.created_at.strftime('%d.%m.%Y')}",
        parse_mode="HTML",
        reply_markup=account_keyboard(),
    )


# ── Рефералы ──────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_referral")
async def cb_referral(cb: CallbackQuery):
    user     = get_or_create_user(cb.from_user.id)
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user.referral_code}"

    from models import SessionLocal, User as UM
    db = SessionLocal()
    try:
        count = db.query(UM).filter(UM.referred_by == user.id).count()
    finally:
        db.close()

    await cb.message.edit_text(
        f"👥 <b>Реферальная программа</b>\n\n"
        f"🎁 За каждого приглашённого: <b>{settings.REFERRAL_BONUS_DAYS} дней</b> подписки\n\n"
        f"Твоя ссылка:\n<code>{ref_link}</code>\n\n"
        f"📊 Приглашено: <b>{count}</b> чел.",
        parse_mode="HTML",
        reply_markup=referral_keyboard(ref_link),
    )


# ── Отзывы ────────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_review")
async def cb_review(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(ReviewStates.waiting_rating)
    await cb.message.edit_text(
        "⭐ <b>Оставить отзыв</b>\n\nВыбери оценку:",
        parse_mode="HTML",
        reply_markup=review_rating_keyboard(),
    )


# ИСПРАВЛЕНО: звёзды отображаются как «1 ★», «2 ★» и т.д.
# Telegram схлопывает повторяющиеся emoji ⭐⭐⭐ в одну кнопку визуально —
# поэтому используем число + одну звезду, чтобы было чётко и читаемо.
@dp.callback_query(F.data.startswith("rate_"), ReviewStates.waiting_rating)
async def process_rating(cb: CallbackQuery, state: FSMContext):
    rating = int(cb.data.split("_")[1])
    await state.update_data(rating=rating)
    await state.set_state(ReviewStates.waiting_text)

    stars_map = {1: "1 ★☆☆☆☆", 2: "2 ★★☆☆☆", 3: "3 ★★★☆☆", 4: "4 ★★★★☆", 5: "5 ★★★★★"}
    stars_display = stars_map.get(rating, f"{rating} ★")

    await cb.message.edit_text(
        f"Оценка: <b>{stars_display}</b>\n\n"
        f"Напиши короткий комментарий\n(или отправь /skip чтобы пропустить):",
        parse_mode="HTML",
        reply_markup=back_menu(),
    )


@dp.message(ReviewStates.waiting_text)
async def process_review_text(message: Message, state: FSMContext):
    data   = await state.get_data()
    rating = data.get("rating", 5)
    text   = None if message.text == "/skip" else message.text
    user   = get_or_create_user(message.from_user.id)
    create_review(user.id, rating, text)
    await state.clear()
    await message.answer(
        "✅ <b>Спасибо за отзыв!</b>\n\nТвоё мнение помогает нам стать лучше.",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# ── Поддержка ─────────────────────────────────────────────────────────────────

@dp.message(Command("support"))
async def cmd_support(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "💬 <b>Поддержка</b>\n\nНапиши нам, и мы поможем!\nСреднее время ответа: до 2 часов.",
        parse_mode="HTML",
        reply_markup=support_keyboard(),
    )


@dp.callback_query(F.data == "menu_support")
async def cb_support(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text(
        "💬 <b>Поддержка</b>\n\nНапиши нам, и мы поможем!\nСреднее время ответа: до 2 часов.",
        parse_mode="HTML",
        reply_markup=support_keyboard(),
    )


@dp.callback_query(F.data == "support_write")
async def support_write(cb: CallbackQuery, state: FSMContext):
    await state.set_state(SupportStates.waiting_message)
    await cb.message.edit_text(
        "✍️ Напиши своё сообщение для поддержки:",
        parse_mode="HTML",
        reply_markup=back_menu(),
    )


@dp.message(SupportStates.waiting_message)
async def process_support(message: Message, state: FSMContext):
    user   = get_or_create_user(message.from_user.id)
    ticket = create_ticket(user.id, message.text)
    for admin_id in settings.admin_ids_list:
        try:
            await bot.send_message(
                admin_id,
                f"🎫 <b>Тикет #{ticket.id}</b>\n"
                f"От: @{message.from_user.username or '—'} (ID: {message.from_user.id})\n\n"
                f"{message.text}\n\nОтветить: /ticket_{ticket.id}",
                parse_mode="HTML",
            )
        except Exception:
            pass
    await state.clear()
    await message.answer(
        f"✅ <b>Сообщение отправлено!</b>\n\nТикет: <b>#{ticket.id}</b>\nОтветим в ближайшее время.",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


@dp.message(Command(commands=["ticket"]))
async def admin_ticket_cmd(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split("_")
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Формат: /ticket_<id>")
        return
    await state.set_state(AdminStates.answer_ticket_text)
    await state.update_data(ticket_id=int(parts[1]))
    await message.answer(f"✍️ Напиши ответ на тикет #{parts[1]}:")


@dp.message(AdminStates.answer_ticket_text)
async def admin_send_answer(message: Message, state: FSMContext):
    data      = await state.get_data()
    ticket_id = data.get("ticket_id")
    answer_ticket(ticket_id, message.text)
    await state.clear()

    from models import SessionLocal, SupportTicket as TM, User as UM
    db = SessionLocal()
    try:
        t = db.query(TM).filter(TM.id == ticket_id).first()
        if t:
            u = db.query(UM).filter(UM.id == t.user_id).first()
            if u:
                try:
                    await bot.send_message(
                        u.telegram_id,
                        f"📩 <b>Ответ на тикет #{ticket_id}:</b>\n\n{message.text}",
                        parse_mode="HTML",
                        reply_markup=main_menu(),
                    )
                except Exception:
                    pass
    finally:
        db.close()
    await message.answer(f"✅ Ответ на тикет #{ticket_id} отправлен!")


# ── Админ-панель ──────────────────────────────────────────────────────────────

@dp.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа")
        return
    await state.clear()
    stats = get_bot_stats()
    await message.answer(
        f"⚙️ <b>Админ-панель</b>\n\n"
        f"👥 Пользователей: <b>{stats['total_users']}</b>\n"
        f"💎 Активных подписок: <b>{stats['active_subs']}</b>\n"
        f"⏳ Ожидают оплаты: <b>{stats['pending_payments']}</b>\n"
        f"💰 Выручка: <b>{stats['revenue']:.0f} ₽</b>\n"
        f"🎫 Открытых тикетов: <b>{stats['open_tickets']}</b>",
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


@dp.callback_query(F.data == "adm_stats")
async def adm_stats(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    stats = get_bot_stats()
    await cb.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: <b>{stats['total_users']}</b>\n"
        f"💎 Активных подписок: <b>{stats['active_subs']}</b>\n"
        f"⏳ Ожидают подтверждения: <b>{stats['pending_payments']}</b>\n"
        f"💰 Выручка: <b>{stats['revenue']:.0f} ₽</b>\n"
        f"🎫 Открытых тикетов: <b>{stats['open_tickets']}</b>",
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


@dp.callback_query(F.data == "adm_broadcast")
async def adm_broadcast_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.broadcast_text)
    await cb.message.edit_text(
        "📢 <b>Рассылка</b>\n\nНапиши текст (поддерживается HTML):",
        parse_mode="HTML",
        reply_markup=back_menu(),
    )


@dp.message(AdminStates.broadcast_text)
async def adm_broadcast_send(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    users = get_all_users()
    sent, failed = 0, 0
    await message.answer(f"⏳ Рассылаю {len(users)} пользователям...")
    for user in users:
        try:
            await bot.send_message(user.telegram_id, message.text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await message.answer(
        f"✅ <b>Рассылка завершена</b>\n\nОтправлено: <b>{sent}</b> · Ошибок: <b>{failed}</b>",
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "adm_confirm_pay")
async def adm_confirm_list(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    pending = get_pending_payments()
    if not pending:
        await cb.message.edit_text("✅ Нет ожидающих платежей", reply_markup=admin_keyboard())
        return
    lines = ["⏳ <b>Ожидающие платежи:</b>\n"]
    for p in pending:
        lines.append(f"#{p.id} · {p.amount:.0f} ₽ · {p.plan} · /confirm_{p.id}")
    await cb.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=admin_keyboard())


@dp.callback_query(F.data == "adm_tickets")
async def adm_tickets_list(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    tickets = get_open_tickets()
    if not tickets:
        await cb.message.edit_text("✅ Открытых тикетов нет", reply_markup=admin_keyboard())
        return
    lines = ["🎫 <b>Открытые тикеты:</b>\n"]
    for t in tickets[:10]:
        lines.append(f"#{t.id} · {t.created_at.strftime('%d.%m')} · /ticket_{t.id}\n{t.message[:80]}")
    await cb.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=admin_keyboard())


# ── Фоновая задача: уведомления об истекающих подписках ──────────────────────

async def notify_expiring():
    while True:
        try:
            from models import SessionLocal, Subscription as SM, User as UM
            db  = SessionLocal()
            now = datetime.now()
            expiring = db.query(SM).filter(
                SM.active == True,
                SM.expires_at <= now + timedelta(days=3),
                SM.expires_at > now,
            ).all()
            for sub in expiring:
                user = db.query(UM).filter(UM.id == sub.user_id).first()
                if user:
                    days = (sub.expires_at - now).days
                    try:
                        await bot.send_message(
                            user.telegram_id,
                            f"⚠️ <b>Подписка истекает через {days} дн.!</b>\n\n"
                            f"Продли, чтобы не потерять доступ 👇",
                            parse_mode="HTML",
                            reply_markup=subscription_plans(),
                        )
                    except Exception:
                        pass
            db.close()
        except Exception as e:
            logger.error(f"notify_expiring error: {e}")
        await asyncio.sleep(86400)


# ── Запуск ────────────────────────────────────────────────────────────────────

async def main():
    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN не задан!")
        return

    init_db()
    logger.info("✅ БД инициализирована")

    ai_ready = bool(os.getenv("OPENAI_API_KEY"))
    logger.info(f"🤖 AI: {'подключён (OpenAI)' if ai_ready else 'демо-режим (OPENAI_API_KEY не задан)'}")

    await bot.set_my_commands([
        BotCommand(command="start",     description="Главное меню"),
        BotCommand(command="account",   description="Личный кабинет"),
        BotCommand(command="subscribe", description="Подписка"),
        BotCommand(command="trial",     description="Триал 7 дней"),
        BotCommand(command="support",   description="Поддержка"),
        BotCommand(command="help",      description="Помощь"),
        BotCommand(command="admin",     description="Админ-панель"),
    ])
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(notify_expiring())
    logger.info("🚀 Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
