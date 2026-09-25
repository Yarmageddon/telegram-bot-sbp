"""
Главный файл бота — все хэндлеры в одном месте, чистая архитектура
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, BotCommand

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

# ── Тарифы ────────────────────────────────────────────────────────────────────
PLANS = {
    "basic":    {"name": "Базовый",    "price": settings.PRICE_BASIC,    "days": 30},
    "pro":      {"name": "Про",        "price": settings.PRICE_PRO,      "days": 30},
    "business": {"name": "Бизнес",     "price": settings.PRICE_BUSINESS, "days": 30},
}


# ── FSM States ────────────────────────────────────────────────────────────────
class PayStates(StatesGroup):
    waiting_proof = State()

class ReviewStates(StatesGroup):
    waiting_rating = State()
    waiting_text = State()

class SupportStates(StatesGroup):
    waiting_message = State()

class AIStates(StatesGroup):
    waiting_question = State()

class DocStates(StatesGroup):
    waiting_pdf = State()
    waiting_text = State()
    waiting_photo = State()

class AdminStates(StatesGroup):
    broadcast_text = State()
    confirm_pay_id = State()
    answer_ticket_id = State()
    answer_ticket_text = State()

class NewsStates(StatesGroup):
    waiting_title = State()
    waiting_content = State()


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids_list


def subscription_status_text(user_id: int) -> str:
    sub = get_active_subscription(user_id)
    trial = get_trial(user_id)
    if sub:
        days = (sub.expires_at - datetime.now()).days
        return f"💎 <b>Подписка:</b> {sub.plan.capitalize()} · ещё {days} дн. (до {sub.expires_at.strftime('%d.%m.%Y')})"
    if trial and trial.used and trial.expires_at > datetime.now():
        days = (trial.expires_at - datetime.now()).days
        return f"🎁 <b>Триал:</b> ещё {days} дн. (до {trial.expires_at.strftime('%d.%m.%Y')})"
    return "❌ <b>Подписка:</b> не активна"


def has_access(user_id: int) -> bool:
    """Проверяет, есть ли у пользователя активная подписка или триал."""
    sub = get_active_subscription(user_id)
    if sub:
        return True
    trial = get_trial(user_id)
    if trial and trial.used and trial.expires_at > datetime.now():
        return True
    return False


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

    # Реферальная система
    if ref_code and ref_code != user.referral_code:
        referrer = get_user_by_ref_code(ref_code)
        if referrer and referrer.id != user.id:
            apply_referral(user.id, referrer.id)
            # Бонус пригласившему — 7 дней подписки
            create_subscription(referrer.id, "referral_bonus", settings.REFERRAL_BONUS_DAYS)
            try:
                await bot.send_message(
                    referrer.telegram_id,
                    f"🎉 По вашей реферальной ссылке зарегистрировался новый пользователь!\n"
                    f"Вы получили <b>{settings.REFERRAL_BONUS_DAYS} дней</b> подписки в подарок! 🎁",
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


# ── /account ──────────────────────────────────────────────────────────────────

@dp.message(Command("account"))
async def cmd_account(message: Message, state: FSMContext):
    await state.clear()
    await show_account(message.from_user.id, message)


async def show_account(telegram_id: int, target):
    user = get_or_create_user(telegram_id)
    stats = get_rating_stats()
    sub_text = subscription_status_text(user.id)
    payments = get_user_payments(user.id)
    total_paid = sum(p.amount for p in payments if p.status == "completed")

    ref_link = f"https://t.me/{(await bot.get_me()).username}?start={user.referral_code}"

    text = (
        f"👤 <b>Личный кабинет</b>\n\n"
        f"<b>Имя:</b> {user.first_name or 'Не указано'}\n"
        f"<b>Username:</b> @{user.username or 'Не указан'}\n"
        f"<b>ID:</b> <code>{user.telegram_id}</code>\n"
        f"<b>Регистрация:</b> {user.created_at.strftime('%d.%m.%Y')}\n\n"
        f"{sub_text}\n\n"
        f"<b>Реферальная ссылка:</b>\n<code>{ref_link}</code>\n\n"
        f"<b>Всего оплачено:</b> {total_paid:.0f} ₽"
    )

    if isinstance(target, Message):
        await target.answer(text, parse_mode="HTML", reply_markup=account_keyboard())
    else:
        await target.message.edit_text(text, parse_mode="HTML", reply_markup=account_keyboard())


# ── Главное меню (callback) ───────────────────────────────────────────────────

@dp.callback_query(F.data == "back_main")
async def cb_back_main(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text(
        "🏠 <b>Главное меню</b>\n\nВыбери раздел:",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# ── Подписка ──────────────────────────────────────────────────────────────────

@dp.message(Command("subscribe"))
@dp.callback_query(F.data == "menu_sub")
async def show_subscription(event, state: FSMContext):
    await state.clear()
    is_cb = isinstance(event, CallbackQuery)
    user_id = event.from_user.id
    user = get_or_create_user(user_id)
    sub_text = subscription_status_text(user.id)

    text = (
        f"💎 <b>Подписка</b>\n\n"
        f"{sub_text}\n\n"
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
        "• API доступ\n"
        "• Персональный менеджер\n"
    )

    if is_cb:
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=subscription_plans())
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=subscription_plans())


@dp.callback_query(F.data.startswith("plan_"))
async def select_plan(cb: CallbackQuery, state: FSMContext):
    plan_key = cb.data.replace("plan_", "")
    plan = PLANS.get(plan_key)
    if not plan:
        await cb.answer("Неизвестный план")
        return

    await state.update_data(plan=plan_key)

    text = (
        f"💳 <b>Оплата: {plan['name']}</b>\n\n"
        f"Сумма: <b>{plan['price']} ₽</b>\n\n"
        f"Переведи на реквизиты:\n"
        f"💳 Карта: <code>{settings.PAYMENT_CARD}</code>\n"
        f"📱 СБП: <code>{settings.PAYMENT_PHONE}</code>\n\n"
        f"В комментарии укажи свой Telegram ID: <code>{cb.from_user.id}</code>\n\n"
        f"После оплаты нажми <b>«✅ Я оплатил»</b> — администратор проверит и активирует подписку."
    )

    # Создаём платёж со статусом pending
    user = get_or_create_user(cb.from_user.id)
    payment = create_payment(user.id, plan["price"], plan_key)
    await state.update_data(payment_id=payment.id)

    # Уведомляем администраторов
    for admin_id in settings.admin_ids_list:
        try:
            await bot.send_message(
                admin_id,
                f"💰 <b>Новый платёж #{payment.id}</b>\n"
                f"Пользователь: @{cb.from_user.username or cb.from_user.id} (ID: {cb.from_user.id})\n"
                f"Тариф: {plan['name']}\n"
                f"Сумма: {plan['price']} ₽\n\n"
                f"Для подтверждения: /confirm_{payment.id}",
                parse_mode="HTML",
            )
        except Exception:
            pass

    await cb.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=payment_confirm(plan_key, plan["price"]),
    )


@dp.callback_query(F.data.startswith("paid_"))
async def payment_confirmed_by_user(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    payment_id = data.get("payment_id")
    plan_key = data.get("plan")

    await cb.message.edit_text(
        "⏳ <b>Платёж отправлен на проверку!</b>\n\n"
        "Администратор проверит оплату и активирует подписку в течение нескольких минут.\n"
        "Вы получите уведомление, как только подписка будет активирована.",
        parse_mode="HTML",
        reply_markup=back_menu(),
    )
    await state.clear()


# Команда для быстрого подтверждения оплаты из чата с ботом
@dp.message(Command(commands=["confirm"]))
async def admin_quick_confirm(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split("_")
    if len(parts) < 2:
        await message.answer("Формат: /confirm_<payment_id>")
        return
    try:
        payment_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный ID платежа")
        return
    await do_confirm_payment(payment_id, message)


async def do_confirm_payment(payment_id: int, message: Message):
    from models import SessionLocal, Payment as PayModel
    db = SessionLocal()
    try:
        p = db.query(PayModel).filter(PayModel.id == payment_id).first()
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
        # Найти telegram_id пользователя
        from models import User as UserModel
        user = db.query(UserModel).filter(UserModel.id == p.user_id).first()
        if user:
            try:
                await bot.send_message(
                    user.telegram_id,
                    f"🎉 <b>Подписка активирована!</b>\n\n"
                    f"Тариф: <b>{plan['name']}</b>\n"
                    f"Действует: <b>{plan['days']} дней</b>\n\n"
                    f"Спасибо за оплату! Используй /start для доступа ко всем функциям.",
                    parse_mode="HTML",
                )
            except Exception:
                pass
        await message.answer(f"✅ Платёж #{payment_id} подтверждён, подписка активирована!")
    finally:
        db.close()


# ── Триал ─────────────────────────────────────────────────────────────────────

@dp.message(Command("trial"))
@dp.callback_query(F.data == "menu_trial")
async def show_trial(event, state: FSMContext):
    await state.clear()
    is_cb = isinstance(event, CallbackQuery)
    user = get_or_create_user(event.from_user.id)
    trial = get_trial(user.id)

    if trial and trial.used:
        if trial.expires_at > datetime.now():
            days = (trial.expires_at - datetime.now()).days
            text = (
                f"🎁 <b>Триал активен</b>\n\n"
                f"Осталось дней: <b>{days}</b>\n"
                f"Истекает: {trial.expires_at.strftime('%d.%m.%Y')}"
            )
        else:
            text = (
                "❌ <b>Триал уже использован</b>\n\n"
                "Оформи подписку, чтобы продолжить пользоваться всеми функциями."
            )
        kb = back_menu()
    else:
        text = (
            "🎁 <b>Пробный период — 7 дней бесплатно!</b>\n\n"
            "Получи полный доступ ко всем функциям бота:\n"
            "• AI-ассистент\n"
            "• Конвертация документов\n"
            "• OCR распознавание\n\n"
            "Активируй один раз, без привязки карты!"
        )
        kb = trial_keyboard()

    if is_cb:
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=kb)


@dp.callback_query(F.data == "activate_trial")
async def activate_trial(cb: CallbackQuery):
    user = get_or_create_user(cb.from_user.id)
    result = start_trial(user.id, days=7)
    if result["success"]:
        await cb.message.edit_text(
            "🎉 <b>Триал активирован на 7 дней!</b>\n\n"
            "Теперь у тебя есть полный доступ ко всем функциям.\n"
            "Используй /start для навигации.",
            parse_mode="HTML",
            reply_markup=back_menu(),
        )
    else:
        await cb.message.edit_text(
            f"❌ {result['message']}\n\nОформи подписку для продолжения.",
            parse_mode="HTML",
            reply_markup=back_menu(),
        )


# ── AI-Ассистент ──────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_ai")
async def show_ai(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text(
        "🤖 <b>AI-Ассистент</b>\n\n"
        "Задай любой вопрос или выбери готовый шаблон:\n\n"
        "• Напишу текст, email, резюме\n"
        "• Объясню сложное простым языком\n"
        "• Помогу с бизнес-задачами\n"
        "• Переведу текст\n"
        "• Проанализирую данные",
        parse_mode="HTML",
        reply_markup=ai_keyboard(),
    )


@dp.callback_query(F.data == "ai_ask")
async def ai_ask(cb: CallbackQuery, state: FSMContext):
    user = get_or_create_user(cb.from_user.id)
    if not has_access(user.id):
        await cb.message.edit_text(
            "🔒 <b>Требуется подписка</b>\n\n"
            "AI-ассистент доступен только по подписке.\n"
            "Активируй триал на 7 дней бесплатно!",
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

    templates = {
        "tpl_email": "Напиши деловое письмо. Укажи кому, по какому поводу и что нужно написать:",
        "tpl_bizplan": "Составлю краткий бизнес-план. Опиши свою идею или бизнес:",
        "tpl_ad": "Напишу рекламный текст. Что продаём? Для кого? Какой тон (серьёзный/весёлый)?",
        "tpl_cv": "Помогу написать резюме. Укажи профессию, опыт и ключевые навыки:",
    }

    prompt_text = templates.get(cb.data, "Напиши свой запрос:")
    await state.set_state(AIStates.waiting_question)
    await state.update_data(template=cb.data)
    await cb.message.edit_text(
        f"📝 {prompt_text}",
        parse_mode="HTML",
        reply_markup=back_menu(),
    )


@dp.message(AIStates.waiting_question)
async def process_ai_question(message: Message, state: FSMContext):
    data = await state.get_data()
    question = message.text.strip()

    await message.answer("⏳ Обрабатываю запрос...")

    # AI-ответ (заглушка — в продакшене подключить OpenAI / Anthropic API)
    response = generate_ai_response(question, data.get("template"))

    await message.answer(
        f"🤖 <b>AI-Ответ:</b>\n\n{response}",
        parse_mode="HTML",
        reply_markup=ai_keyboard(),
    )
    await state.clear()


def generate_ai_response(question: str, template: str = None) -> str:
    """
    Заглушка AI-ответа.
    В продакшене: заменить на вызов OpenAI/Anthropic API.
    """
    q = question.lower()
    if template == "tpl_email":
        return (
            f"Уважаемый получатель,\n\n"
            f"Пишу вам по следующему вопросу: {question}\n\n"
            f"Буду рад вашему ответу.\n\nС уважением"
        )
    if template == "tpl_cv":
        return (
            f"📄 Резюме\n\n"
            f"Профессиональная сводка: {question}\n\n"
            f"Опыт работы: [укажите опыт]\n"
            f"Образование: [укажите образование]\n"
            f"Навыки: [укажите навыки]"
        )
    if "привет" in q or "hello" in q:
        return "Привет! Чем могу помочь? Задай свой вопрос."
    if "цена" in q or "стоимость" in q or "тариф" in q:
        return "💎 Тарифы:\n• Базовый — 299₽/мес\n• Про — 799₽/мес\n• Бизнес — 1999₽/мес\n\nПопробуй 7 дней бесплатно!"
    return (
        f"По вашему запросу «{question[:100]}»:\n\n"
        "Это демо-режим AI-ассистента. Для полноценной работы "
        "необходимо подключить API языковой модели (OpenAI / Anthropic).\n\n"
        "💡 Обратитесь к администратору для настройки."
    )


# ── Документы ─────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_docs")
async def show_docs(cb: CallbackQuery, state: FSMContext):
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
async def doc_pdf_to_text(cb: CallbackQuery, state: FSMContext):
    await state.set_state(DocStates.waiting_pdf)
    await cb.message.edit_text(
        "📄 <b>PDF → Текст</b>\n\nОтправь PDF-файл:",
        parse_mode="HTML",
        reply_markup=back_menu(),
    )


@dp.callback_query(F.data == "doc_txt2pdf")
async def doc_text_to_pdf(cb: CallbackQuery, state: FSMContext):
    await state.set_state(DocStates.waiting_text)
    await cb.message.edit_text(
        "📝 <b>Текст → PDF</b>\n\nОтправь текст, который нужно преобразовать в PDF:",
        parse_mode="HTML",
        reply_markup=back_menu(),
    )


@dp.callback_query(F.data == "doc_ocr")
async def doc_ocr(cb: CallbackQuery, state: FSMContext):
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
        import os, uuid
        from pathlib import Path
        from database import get_or_create_user as _

        file_info = await bot.get_file(doc.file_id)
        tmp_path = f"/tmp/{uuid.uuid4().hex}.pdf"
        await bot.download_file(file_info.file_path, tmp_path)

        from documents import convert_pdf_to_text
        ok, msg, text = convert_pdf_to_text(tmp_path)
        os.remove(tmp_path)

        if ok:
            # Telegram ограничение — 4096 символов
            chunks = [text[i:i+4000] for i in range(0, min(len(text), 12000), 4000)]
            for chunk in chunks:
                await message.answer(f"📄 <b>Текст из PDF:</b>\n\n<code>{chunk}</code>", parse_mode="HTML")
        else:
            await message.answer(f"❌ {msg}", reply_markup=back_menu())
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=back_menu())
    await state.clear()


@dp.message(DocStates.waiting_text)
async def handle_text_to_pdf(message: Message, state: FSMContext):
    text = message.text
    if not text:
        await message.answer("❌ Нужен текст. Попробуй ещё раз.")
        return
    await message.answer("⏳ Создаю PDF...")
    try:
        from documents import convert_text_to_pdf
        ok, msg, path = convert_text_to_pdf(text)
        if ok:
            from aiogram.types import FSInputFile
            await message.answer_document(FSInputFile(path), caption="✅ PDF готов!")
            import os
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
        import uuid, os
        if message.photo:
            file_id = message.photo[-1].file_id
            ext = "jpg"
        else:
            file_id = message.document.file_id
            ext = message.document.file_name.split(".")[-1] if "." in message.document.file_name else "jpg"

        file_info = await bot.get_file(file_id)
        tmp_path = f"/tmp/{uuid.uuid4().hex}.{ext}"
        await bot.download_file(file_info.file_path, tmp_path)

        from documents import ocr_from_image
        ok, msg, text = ocr_from_image(tmp_path)
        os.remove(tmp_path)

        if ok:
            await message.answer(f"🔍 <b>Распознанный текст:</b>\n\n<code>{text[:4000]}</code>", parse_mode="HTML")
        else:
            await message.answer(f"❌ {msg}", reply_markup=back_menu())
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=back_menu())
    await state.clear()


# ── Личный кабинет ────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_account")
async def cb_account(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_account(cb.from_user.id, cb)


@dp.callback_query(F.data == "acc_payments")
async def cb_acc_payments(cb: CallbackQuery):
    user = get_or_create_user(cb.from_user.id)
    payments = get_user_payments(user.id)
    if not payments:
        text = "💳 <b>История платежей</b>\n\nПлатежей пока нет."
    else:
        lines = ["💳 <b>История платежей:</b>\n"]
        for p in payments:
            emoji = "✅" if p.status == "completed" else "⏳"
            lines.append(f"{emoji} {p.amount:.0f} ₽ · {p.plan or '-'} · {p.created_at.strftime('%d.%m.%Y')}")
        text = "\n".join(lines)
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=account_keyboard())


@dp.callback_query(F.data == "acc_stats")
async def cb_acc_stats(cb: CallbackQuery):
    user = get_or_create_user(cb.from_user.id)
    rating_stats = get_rating_stats()
    await cb.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"Общий рейтинг бота: ⭐ {rating_stats['average']} ({rating_stats['total']} отзывов)\n\n"
        f"Твой аккаунт активен с {user.created_at.strftime('%d.%m.%Y')}",
        parse_mode="HTML",
        reply_markup=account_keyboard(),
    )


# ── Рефералы ──────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_referral")
async def show_referral(cb: CallbackQuery):
    user = get_or_create_user(cb.from_user.id)
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user.referral_code}"

    # Считаем рефералов
    from models import SessionLocal, User as UserModel
    db = SessionLocal()
    try:
        referrals_count = db.query(UserModel).filter(UserModel.referred_by == user.id).count()
    finally:
        db.close()

    await cb.message.edit_text(
        f"👥 <b>Реферальная программа</b>\n\n"
        f"Приглашай друзей и получай бонусы!\n\n"
        f"🎁 За каждого приглашённого: <b>{settings.REFERRAL_BONUS_DAYS} дней</b> подписки\n\n"
        f"Твоя ссылка:\n<code>{ref_link}</code>\n\n"
        f"📊 Приглашено: <b>{referrals_count}</b> чел.",
        parse_mode="HTML",
        reply_markup=referral_keyboard(ref_link),
    )


# ── Отзывы ────────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "menu_review")
async def show_review(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(ReviewStates.waiting_rating)
    await cb.message.edit_text(
        "⭐ <b>Оставить отзыв</b>\n\nОцени бота:",
        parse_mode="HTML",
        reply_markup=review_rating_keyboard(),
    )


@dp.callback_query(F.data.startswith("rate_"), ReviewStates.waiting_rating)
async def process_rating(cb: CallbackQuery, state: FSMContext):
    rating = int(cb.data.split("_")[1])
    await state.update_data(rating=rating)
    await state.set_state(ReviewStates.waiting_text)
    stars = "⭐" * rating
    await cb.message.edit_text(
        f"Оценка: {stars}\n\nНапиши короткий комментарий (или /skip чтобы пропустить):",
        parse_mode="HTML",
        reply_markup=back_menu(),
    )


@dp.message(ReviewStates.waiting_text)
async def process_review_text(message: Message, state: FSMContext):
    data = await state.get_data()
    rating = data.get("rating", 5)
    text = None if message.text == "/skip" else message.text
    user = get_or_create_user(message.from_user.id)
    create_review(user.id, rating, text)
    await state.clear()
    await message.answer(
        "✅ <b>Спасибо за отзыв!</b>\n\nТвоё мнение помогает нам стать лучше.",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# ── Поддержка ─────────────────────────────────────────────────────────────────

@dp.message(Command("support"))
@dp.callback_query(F.data == "menu_support")
async def show_support(event, state: FSMContext):
    await state.clear()
    is_cb = isinstance(event, CallbackQuery)
    text = (
        "💬 <b>Поддержка</b>\n\n"
        "Напиши нам, и мы поможем!\n"
        "Среднее время ответа: до 2 часов."
    )
    if is_cb:
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=support_keyboard())
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=support_keyboard())


@dp.callback_query(F.data == "support_write")
async def support_write(cb: CallbackQuery, state: FSMContext):
    await state.set_state(SupportStates.waiting_message)
    await cb.message.edit_text(
        "✍️ Напиши своё сообщение для поддержки:",
        parse_mode="HTML",
        reply_markup=back_menu(),
    )


@dp.message(SupportStates.waiting_message)
async def process_support_message(message: Message, state: FSMContext):
    user = get_or_create_user(message.from_user.id)
    ticket = create_ticket(user.id, message.text)

    # Уведомляем администраторов
    for admin_id in settings.admin_ids_list:
        try:
            await bot.send_message(
                admin_id,
                f"🎫 <b>Новый тикет #{ticket.id}</b>\n"
                f"От: @{message.from_user.username or message.from_user.id} (ID: {message.from_user.id})\n\n"
                f"<b>Сообщение:</b>\n{message.text}\n\n"
                f"Ответить: /ticket_{ticket.id}",
                parse_mode="HTML",
            )
        except Exception:
            pass

    await state.clear()
    await message.answer(
        f"✅ <b>Сообщение отправлено!</b>\n\n"
        f"Номер тикета: <b>#{ticket.id}</b>\n"
        f"Мы ответим в ближайшее время.",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# Команда для ответа на тикет (для админа)
@dp.message(Command(commands=["ticket"]))
async def admin_answer_ticket_cmd(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split("_")
    if len(parts) < 2:
        await message.answer("Формат: /ticket_<id>")
        return
    try:
        ticket_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный ID тикета")
        return
    await state.set_state(AdminStates.answer_ticket_text)
    await state.update_data(ticket_id=ticket_id)
    await message.answer(f"✍️ Напиши ответ на тикет #{ticket_id}:")


@dp.message(AdminStates.answer_ticket_text)
async def admin_send_ticket_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    answer_ticket(ticket_id, message.text)

    # Найти пользователя тикета и отправить ответ
    from models import SessionLocal, SupportTicket as TicketModel, User as UserModel
    db = SessionLocal()
    try:
        t = db.query(TicketModel).filter(TicketModel.id == ticket_id).first()
        if t:
            user = db.query(UserModel).filter(UserModel.id == t.user_id).first()
            if user:
                try:
                    await bot.send_message(
                        user.telegram_id,
                        f"📩 <b>Ответ на ваш тикет #{ticket_id}:</b>\n\n{message.text}",
                        parse_mode="HTML",
                        reply_markup=main_menu(),
                    )
                except Exception:
                    pass
    finally:
        db.close()

    await state.clear()
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
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
        f"💎 Активных подписок: <b>{stats['active_subs']}</b>\n"
        f"⏳ Ожидают подтверждения: <b>{stats['pending_payments']}</b>\n"
        f"💰 Общая выручка: <b>{stats['revenue']:.0f} ₽</b>\n"
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
        "📢 <b>Рассылка</b>\n\nНапиши текст рассылки (поддерживается HTML):",
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
        await asyncio.sleep(0.05)  # Throttle: 20 сообщений/сек
    await message.answer(
        f"✅ <b>Рассылка завершена</b>\n\n"
        f"Отправлено: <b>{sent}</b>\n"
        f"Ошибок: <b>{failed}</b>",
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "adm_confirm_pay")
async def adm_confirm_pay_list(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    pending = get_pending_payments()
    if not pending:
        await cb.message.edit_text(
            "✅ Нет ожидающих платежей",
            reply_markup=admin_keyboard(),
        )
        return
    lines = ["⏳ <b>Ожидающие платежи:</b>\n"]
    for p in pending:
        lines.append(f"#{p.id} · {p.amount:.0f} ₽ · {p.plan} · user_id={p.user_id}\n/confirm_{p.id}")
    await cb.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


@dp.callback_query(F.data == "adm_tickets")
async def adm_tickets_list(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    tickets = get_open_tickets()
    if not tickets:
        await cb.message.edit_text(
            "✅ Открытых тикетов нет",
            reply_markup=admin_keyboard(),
        )
        return
    lines = ["🎫 <b>Открытые тикеты:</b>\n"]
    for t in tickets[:10]:
        lines.append(f"#{t.id} · user_id={t.user_id} · {t.created_at.strftime('%d.%m')}\n{t.message[:80]}...\n/ticket_{t.id}")
    await cb.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


# ── Уведомления об истекающих подписках ──────────────────────────────────────

async def notify_expiring_subscriptions():
    """Запускается раз в сутки — предупреждает об истекающих подписках."""
    while True:
        try:
            from models import SessionLocal, Subscription as SubModel, User as UserModel
            db = SessionLocal()
            soon = datetime.now() + timedelta(days=3)
            expiring = db.query(SubModel).filter(
                SubModel.active == True,
                SubModel.expires_at <= soon,
                SubModel.expires_at > datetime.now(),
            ).all()
            for sub in expiring:
                user = db.query(UserModel).filter(UserModel.id == sub.user_id).first()
                if user:
                    days = (sub.expires_at - datetime.now()).days
                    try:
                        await bot.send_message(
                            user.telegram_id,
                            f"⚠️ <b>Подписка истекает!</b>\n\n"
                            f"Осталось <b>{days} дн.</b> до окончания подписки «{sub.plan}».\n"
                            f"Продли подписку, чтобы не потерять доступ! 👇",
                            parse_mode="HTML",
                            reply_markup=subscription_plans(),
                        )
                    except Exception:
                        pass
            db.close()
        except Exception as e:
            logger.error(f"Ошибка уведомлений: {e}")
        await asyncio.sleep(86400)  # 24 часа


# ── Запуск ────────────────────────────────────────────────────────────────────

async def main():
    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN не задан! Добавь в переменные окружения.")
        return

    init_db()
    logger.info("✅ БД инициализирована")

    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="account", description="Личный кабинет"),
        BotCommand(command="subscribe", description="Подписка"),
        BotCommand(command="trial", description="Триал 7 дней"),
        BotCommand(command="support", description="Поддержка"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="admin", description="Админ-панель"),
    ])

    await bot.delete_webhook(drop_pending_updates=True)

    # Запускаем фоновые задачи
    asyncio.create_task(notify_expiring_subscriptions())

    logger.info("🚀 Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
