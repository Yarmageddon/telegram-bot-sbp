"""
Telegram Bot v2 - Полная версия со всеми функциями
"""
import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)

from config import settings
from models import init_db, SessionLocal, User, Subscription, Payment
from database import get_or_create_user, get_active_subscription, create_payment
from keyboards import main_menu_keyboard, subscription_keyboard, payment_keyboard
from keyboards_v2 import (
    main_menu_v2_keyboard, subscription_menu_keyboard, trial_keyboard,
    documents_keyboard, ocr_keyboard, review_rating_keyboard,
    review_category_keyboard, account_keyboard, ai_assistant_keyboard,
    back_to_menu_keyboard, earthworks_menu_keyboard, earthworks_goals_keyboard,
    npa_qa_keyboard
)
from models_v2 import (
    SubscriptionPlan, Trial, Review, NewsPost, Document,
    DocumentTemplate, PersonalStats
)
from trial import start_trial, check_trial_status
from subscription_upgrade import get_all_plans, get_current_plan, upgrade_subscription
from ai_assistant import get_ai_response, get_product_consultation
from reviews import create_review, get_user_reviews, get_rating_stats
from documents import (
    convert_pdf_to_text, convert_text_to_pdf, ocr_from_image,
    save_uploaded_file, get_file_extension
)
from personal_account import (
    get_account_info, format_account_info, get_payment_history,
    format_payment_history, update_stats
)
from notifications import notification_scheduler
from notifications_v2 import create_news, broadcast_news
from earthworks import get_goals_by_type, search_npa_answer, format_npa_answer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=settings.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# ============= STATES =============

class SubscriptionStates(StatesGroup):
    waiting_for_plan_selection = State()
    waiting_for_payment_confirmation = State()
    waiting_for_promo_code = State()


class SupportStates(StatesGroup):
    waiting_for_message = State()
    waiting_for_response = State()


class ReviewStates(StatesGroup):
    waiting_for_rating = State()
    waiting_for_text = State()
    waiting_for_suggestion = State()


class AIStates(StatesGroup):
    waiting_for_question = State()


class DocumentStates(StatesGroup):
    waiting_for_file = State()
    waiting_for_target_format = State()
    waiting_for_template_data = State()


class NewsStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_content = State()


class EarthworksStates(StatesGroup):
    waiting_for_work_type = State()
    waiting_for_goal = State()
    waiting_for_details = State()
    waiting_for_confirmation = State()


class NPAQAStates(StatesGroup):
    waiting_for_question = State()


# ============= БАЗОВЫЕ КОМАНДЫ =============

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Главная команда"""
    await state.clear()

    db = SessionLocal()
    try:
        user = get_or_create_user(
            db, message.from_user.id, message.from_user.username,
            message.from_user.first_name, message.from_user.last_name
        )
    finally:
        db.close()

    welcome_text = (
        "👋 <b>Добро пожаловать!</b>\n\n"
        "✨ <b>Возможности бота:</b>\n\n"
        "🏗 <b>Земляные работы:</b> ордера, уведомления МПГУ/ИАС УГД\n"
        "🤖 <b>ИИ-помощник НПА:</b> ответы на вопросы по постановлениям\n"
        "💎 <b>Подписки:</b> оформление, смена тарифа, триал\n"
        "📄 <b>Документы:</b> конвертация PDF/Word/Excel\n"
        "🔍 <b>OCR:</b> распознавание текста с фото\n"
        "⭐ <b>Отзывы:</b> оценка и предложения\n"
        "👤 <b>Личный кабинет:</b> статистика, история\n\n"
        "Выберите раздел:"
    )

    await message.answer(
        welcome_text,
        parse_mode="HTML",
        reply_markup=main_menu_v2_keyboard()
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Помощь"""
    help_text = (
        "📚 <b>Команды бота:</b>\n\n"
        "/start - Главное меню\n"
        "/account - Личный кабинет\n"
        "/subscribe - Оформить подписку\n"
        "/trial - Активировать триал\n"
        "/documents - Работа с документами\n"
        "/ocr - Распознавание текста\n"
        "/review - Оставить отзыв\n"
        "/support - Поддержка\n"
        "/help - Эта справка\n\n"
        "💡 Совет: используйте кнопки меню для быстрого доступа!"
    )
    await message.answer(help_text, parse_mode="HTML")


@dp.message(Command("account"))
async def cmd_account(message: Message):
    """Личный кабинет"""
    db = SessionLocal()
    try:
        user = get_or_create_user(db, message.from_user.id)
        info = get_account_info(user.id)
        text = format_account_info(info)
    finally:
        db.close()

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=account_keyboard()
    )


@dp.message(Command("trial"))
async def cmd_trial(message: Message):
    """Команда триал-периода"""
    db = SessionLocal()
    try:
        user = get_or_create_user(db, message.from_user.id)
        status = check_trial_status(user.id)
    finally:
        db.close()

    if status.get("used"):
        if status["days_left"] > 0:
            text = (
                f"🎁 <b>Триал-период активен</b>\n\n"
                f"⏳ Осталось дней: {status['days_left']}\n"
                f"📅 Истекает: {status['expires_at'].strftime('%d.%m.%Y')}"
            )
        else:
            text = (
                "❌ <b>Триал-период уже использован</b>\n\n"
                "Оформите подписку для продолжения использования."
            )
    else:
        text = (
            "🎁 <b>Активируйте триал-период!</b>\n\n"
            "✨ 7 дней бесплатного доступа ко всем функциям\n"
            "💎 Полный функционал без ограничений\n"
            "🚀 Начните прямо сейчас!"
        )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=trial_keyboard()
    )


@dp.message(Command("support"))
async def cmd_support(message: Message, state: FSMContext):
    """Поддержка"""
    await state.set_state(SupportStates.waiting_for_message)

    text = (
        "💬 <b>Поддержка</b>\n\n"
        "Опишите ваш вопрос или проблему, и мы свяжемся с вами в ближайшее время."
    )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=back_to_menu_keyboard()
    )


@dp.message(SupportStates.waiting_for_message)
async def process_support_message(message: Message, state: FSMContext):
    """Обработка сообщения в поддержку"""
    await state.clear()

    # Уведомляем админов
    for admin_id in settings.admin_ids_list:
        try:
            await bot.send_message(
                admin_id,
                f"💬 <b>Новое сообщение в поддержку</b>\n\n"
                f"От: @{message.from_user.username or message.from_user.id}\n"
                f"Сообщение: {message.text}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error notifying admin: {e}")

    await message.answer(
        "✅ <b>Сообщение отправлено!</b>\n\nМы свяжемся с вами в ближайшее время.",
        parse_mode="HTML",
        reply_markup=back_to_menu_keyboard()
    )


# ============= ЗЕМЛЯНЫЕ РАБОТЫ =============

@dp.callback_query(F.data == "menu_earthworks")
async def menu_earthworks(callback_query: CallbackQuery, state: FSMContext):
    """Меню земляных работ"""
    await state.clear()
    await state.set_state(EarthworksStates.waiting_for_work_type)

    text = (
        "🏗 <b>Земляные работы</b>\n\n"
        "Выберите тип услуги:\n\n"
        "📋 <b>Ордер</b> - оформление ордера на земляные работы\n"
        "📢 <b>Плановое уведомление МПГУ</b> - уведомление в МПГУ\n"
        "📡 <b>Плановое уведомление ИАС УГД</b> - уведомление в ИАС УГД\n"
        "🚨 <b>Аварийное уведомление</b> - уведомление об аварийных работах"
    )

    await callback_query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=earthworks_menu_keyboard()
    )
    await callback_query.answer()


@dp.callback_query(F.data.startswith("earthworks_"))
async def process_work_type(callback_query: CallbackQuery, state: FSMContext):
    """Обработка выбора типа работы"""
    work_type = callback_query.data.replace("earthworks_", "")
    await state.update_data(work_type=work_type)

    if work_type == "emergency":
        # Для аварийного уведомления не нужен выбор цели
        await state.set_state(EarthworksStates.waiting_for_details)
        text = (
            "🚨 <b>Аварийное уведомление</b>\n\n"
            "Опишите детали аварийной ситуации:\n"
            "• Адрес проведения работ\n"
            "• Характер аварии\n"
            "• Сроки начала и окончания работ\n"
            "• Контактная информация"
        )
        await callback_query.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard()
        )
    else:
        # Для остальных типов нужен выбор цели
        await state.set_state(EarthworksStates.waiting_for_goal)
        goals = get_goals_by_type(work_type)

        work_type_names = {
            "order": "📋 Ордер",
            "mpgu_planned": "📢 Плановое уведомление МПГУ",
            "iasugd_planned": "📡 Плановое уведомление ИАС УГД"
        }

        text = (
            f"{work_type_names.get(work_type, 'Работа')}\n\n"
            f"Выберите цель проведения работ:\n\n"
            f"📚 Основание: НПА Москвы"
        )

        await callback_query.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=earthworks_goals_keyboard(work_type)
        )

    await callback_query.answer()


@dp.callback_query(F.data.startswith("goal_"))
async def process_goal_selection(callback_query: CallbackQuery, state: FSMContext):
    """Обработка выбора цели"""
    parts = callback_query.data.split("_", 2)
    if len(parts) != 3:
        await callback_query.answer("❌ Ошибка выбора цели", show_alert=True)
        return

    work_type = parts[1]
    goal_key = parts[2]

    goals = get_goals_by_type(work_type)
    goal_text = goals.get(goal_key, "Неизвестная цель")

    await state.update_data(goal_key=goal_key, goal_text=goal_text)
    await state.set_state(EarthworksStates.waiting_for_details)

    text = (
        f"✅ Выбрана цель: {goal_text}\n\n"
        f"Опишите детали заявки:\n"
        f"• Адрес проведения работ\n"
        f"• Сроки начала и окончания работ\n"
        f"• Объем работ\n"
        f"• Контактная информация\n"
        f"• Дополнительные сведения"
    )

    await callback_query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=back_to_menu_keyboard()
    )
    await callback_query.answer()


@dp.message(EarthworksStates.waiting_for_details)
async def process_work_details(message: Message, state: FSMContext):
    """Обработка деталей заявки"""
    data = await state.get_data()
    work_type = data.get("work_type")
    goal_text = data.get("goal_text", "Не указана")
    details = message.text

    await state.update_data(details=details)
    await state.set_state(EarthworksStates.waiting_for_confirmation)

    work_type_names = {
        "order": "📋 Ордер",
        "mpgu_planned": "📢 Плановое уведомление МПГУ",
        "iasugd_planned": "📡 Плановое уведомление ИАС УГД",
        "emergency": "🚨 Аварийное уведомление"
    }

    text = (
        f"📝 <b>Проверьте данные заявки</b>\n\n"
        f"<b>Тип работы:</b> {work_type_names.get(work_type, 'Неизвестно')}\n"
        f"<b>Цель:</b> {goal_text}\n"
        f"<b>Детали:</b>\n{details}\n\n"
        f"Подтвердить отправку заявки?"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_earthworks"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_earthworks")
        ]
    ])

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "confirm_earthworks")
async def confirm_earthworks(callback_query: CallbackQuery, state: FSMContext):
    """Подтверждение заявки"""
    data = await state.get_data()

    # Здесь можно добавить сохранение заявки в базу данных
    # и отправку уведомления администраторам

    await state.clear()

    text = (
        "✅ <b>Заявка отправлена!</b>\n\n"
        "Ваша заявка принята в обработку.\n"
        "Мы свяжемся с вами в ближайшее время.\n\n"
        "📞 Если у вас есть срочные вопросы, используйте /support"
    )

    await callback_query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=back_to_menu_keyboard()
    )
    await callback_query.answer()


@dp.callback_query(F.data == "cancel_earthworks")
async def cancel_earthworks(callback_query: CallbackQuery, state: FSMContext):
    """Отмена заявки"""
    await state.clear()
    await callback_query.message.edit_text(
        "❌ Заявка отменена",
        reply_markup=back_to_menu_keyboard()
    )
    await callback_query.answer()


# ============= ВОПРОС-ОТВЕТ ПО НПА =============

@dp.callback_query(F.data == "menu_npa_qa")
async def menu_npa_qa(callback_query: CallbackQuery, state: FSMContext):
    """Меню вопрос-ответ по НПА"""
    await state.clear()

    text = (
        "📚 <b>Вопрос-ответ по НПА</b>\n\n"
        "Здесь вы можете получить ответы на вопросы по нормативно-правовым актам Москвы:\n\n"
        "• 283-ПП - О проведении земляных работ в уведомительном порядке\n"
        "• 284-ПП - Об утверждении порядка оформления ордеров\n"
        "• 299-ПП - Правила проведения земляных работ\n"
        "• 1112-ПП - Порядок уведомления о проведении аварийно-восстановительных работ\n\n"
        "Выберите тему или задайте свой вопрос:"
    )

    await callback_query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=npa_qa_keyboard()
    )
    await callback_query.answer()


@dp.callback_query(F.data.startswith("npa_q_"))
async def process_npa_question(callback_query: CallbackQuery, state: FSMContext):
    """Обработка вопросов по НПА"""
    question_key = callback_query.data.replace("npa_q_", "")

    # Маппинг ключей на темы
    topic_mapping = {
        "order": "ордер",
        "order_terms": "сроки ордер",
        "mpgu": "уведомление мпгу",
        "iasugd": "уведомление иас угд",
        "emergency": "аварийные работы",
        "restoration": "восстановление благоустройства"
    }

    topic = topic_mapping.get(question_key, question_key)
    answer = search_npa_answer(topic)

    if answer:
        text = format_npa_answer(answer)
    else:
        text = "❓ Не удалось найти ответ на этот вопрос. Попробуйте переформулировать или обратитесь в поддержку."

    await callback_query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к вопросам", callback_data="menu_npa_qa")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
        ])
    )
    await callback_query.answer()


@dp.callback_query(F.data == "npa_q_custom")
async def process_custom_npa_question(callback_query: CallbackQuery, state: FSMContext):
    """Обработка пользовательского вопроса по НПА"""
    await state.set_state(NPAQAStates.waiting_for_question)

    text = (
        "❓ <b>Задайте вопрос по НПА</b>\n\n"
        "Введите ваш вопрос по нормативно-правовым актам Москвы.\n\n"
        "Примеры вопросов:\n"
        "• Какие сроки оформления ордера?\n"
        "• Что такое уведомление МПГУ?\n"
        "• Как проводятся аварийные работы?\n"
        "• Какие документы нужны для уведомления?"
    )

    await callback_query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="menu_npa_qa")]
        ])
    )
    await callback_query.answer()


@dp.message(NPAQAStates.waiting_for_question)
async def process_npa_question_text(message: Message, state: FSMContext):
    """Обработка текста вопроса по НПА"""
    question = message.text
    answer = search_npa_answer(question)

    if answer:
        text = format_npa_answer(answer)
    else:
        text = (
            "❓ Не удалось найти точный ответ на ваш вопрос в базе знаний НПА.\n\n"
            "Рекомендуем:\n"
            "• Переформулировать вопрос\n"
            "• Использовать кнопки меню для выбора темы\n"
            "• Обратиться в поддержку через /support"
        )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Задать другой вопрос", callback_data="npa_q_custom")],
            [InlineKeyboardButton(text="📚 Меню вопросов", callback_data="menu_npa_qa")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_menu")]
        ])
    )
    await state.clear()


# ============= НАВИГАЦИЯ =============

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback_query: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()

    text = (
        "🏠 <b>Главное меню</b>\n\n"
        "Выберите раздел:"
    )

    await callback_query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=main_menu_v2_keyboard()
    )
    await callback_query.answer()


@dp.callback_query(F.data == "menu_subscription")
async def menu_subscription(callback_query: CallbackQuery, state: FSMContext):
    """Меню подписки"""
    await state.clear()

    text = (
        "💎 <b>Подписки</b>\n\n"
        "Управляйте вашей подпиской:\n"
        "• Оформление новой подписки\n"
        "• Смена тарифа\n"
        "• Проверка статуса"
    )

    await callback_query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=subscription_menu_keyboard()
    )
    await callback_query.answer()


@dp.callback_query(F.data == "menu_trial")
async def menu_trial(callback_query: CallbackQuery, state: FSMContext):
    """Меню триала"""
    await state.clear()

    db = SessionLocal()
    try:
        user = get_or_create_user(db, callback_query.from_user.id)
        status = check_trial_status(user.id)
    finally:
        db.close()

    if status.get("used") and status["days_left"] > 0:
        text = (
            f"🎁 <b>Триал-период активен</b>\n\n"
            f"⏳ Осталось дней: {status['days_left']}"
        )
    else:
        text = (
            "🎁 <b>Триал-период</b>\n\n"
            "✨ 7 дней бесплатного доступа\n"
            "💎 Полный функционал"
        )

    await callback_query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=trial_keyboard()
    )
    await callback_query.answer()


@dp.callback_query(F.data == "activate_trial")
async def activate_trial(callback_query: CallbackQuery, state: FSMContext):
    """Активация триала"""
    db = SessionLocal()
    try:
        user = get_or_create_user(db, callback_query.from_user.id)
        result = start_trial(user.id, days=7)
    finally:
        db.close()

    await callback_query.message.edit_text(
        f"✅ {result['message']}",
        reply_markup=back_to_menu_keyboard()
    )
    await callback_query.answer()


@dp.callback_query(F.data == "menu_documents")
async def menu_documents(callback_query: CallbackQuery, state: FSMContext):
    """Меню документов"""
    await state.clear()

    text = (
        "📄 <b>Работа с документами</b>\n\n"
        "Выберите операцию:"
    )

    await callback_query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=documents_keyboard()
    )
    await callback_query.answer()


@dp.callback_query(F.data == "menu_ocr")
async def menu_ocr(callback_query: CallbackQuery, state: FSMContext):
    """Меню OCR"""
    await state.clear()
    await state.set_state(DocumentStates.waiting_for_file)
    await state.update_data(operation="ocr")

    text = (
        "🔍 <b>OCR - Распознавание текста</b>\n\n"
        "Отправьте фото с текстом для распознавания.\n\n"
        "💡 Поддерживаются языки: русский, английский"
    )

    await callback_query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=back_to_menu_keyboard()
    )
    await callback_query.answer()


@dp.callback_query(F.data == "menu_account")
async def menu_account(callback_query: CallbackQuery, state: FSMContext):
    """Личный кабинет"""
    await state.clear()

    db = SessionLocal()
    try:
        user = get_or_create_user(db, callback_query.from_user.id)
        info = get_account_info(user.id)
        text = format_account_info(info)
    finally:
        db.close()

    await callback_query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=account_keyboard()
    )
    await callback_query.answer()


@dp.callback_query(F.data == "menu_reviews")
async def menu_reviews(callback_query: CallbackQuery, state: FSMContext):
    """Меню отзывов"""
    await state.clear()
    await state.set_state(ReviewStates.waiting_for_rating)

    text = (
        "⭐ <b>Оставьте отзыв</b>\n\n"
        "Оцените качество нашего сервиса от 1 до 5 звезд:"
    )

    await callback_query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=review_rating_keyboard()
    )
    await callback_query.answer()


@dp.callback_query(F.data.startswith("rate_"))
async def process_rating(callback_query: CallbackQuery, state: FSMContext):
    """Обработка рейтинга"""
    rating = int(callback_query.data.split("_")[1])
    await state.update_data(rating=rating)
    await state.set_state(ReviewStates.waiting_for_text)

    text = (
        f"⭐ Вы поставили: {rating} звезд\n\n"
        "Напишите комментарий (или отправьте /skip):"
    )

    await callback_query.message.edit_text(
        text,
        reply_markup=back_to_menu_keyboard()
    )
    await callback_query.answer()


@dp.message(ReviewStates.waiting_for_text)
async def process_review_text(message: Message, state: FSMContext):
    """Обработка текста отзыва"""
    data = await state.get_data()
    rating = data.get("rating", 5)
    text = message.text if message.text != "/skip" else None

    db = SessionLocal()
    try:
        user = get_or_create_user(db, message.from_user.id)
        result = create_review(user.id, rating, text)
    finally:
        db.close()

    await state.clear()
    await message.answer(
        f"✅ {result['message']}",
        reply_markup=back_to_menu_keyboard()
    )


# ============= ЗАПУСК БОТА =============

async def on_startup():
    """Действия при запуске бота"""
    logger.info("🚀 Starting bot v2 with all features...")

    # Инициализация БД
    init_db()
    logger.info("✅ Database initialized")

    # Запуск планировщика уведомлений
    asyncio.create_task(notification_scheduler())
    logger.info("✅ Notification scheduler started")


async def on_shutdown():
    """Действия при остановке бота"""
    logger.info("🛑 Stopping bot...")
    await bot.session.close()


# Регистрируем хуки
dp.startup.register(on_startup)
dp.shutdown.register(on_shutdown)


if __name__ == "__main__":
    from aiogram.types import BotCommand

    async def main():
        # Установка команд бота
        await bot.set_my_commands([
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="help", description="Помощь"),
            BotCommand(command="account", description="Личный кабинет"),
            BotCommand(command="trial", description="Активировать триал"),
            BotCommand(command="support", description="Поддержка")
        ])

        # Удаление вебхука и запуск polling
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

    asyncio.run(main())
