"""
Telegram Bot v2 - Полная версия со всеми функциями
1. Апгрейд/даунгрейд тарифов
2. Триал-периоды
3. AI-ассистент 24/7
4. Консультации по продукту
5. Отзывы и рейтинги
6. Push-уведомления о новостях
7. Конвертация PDF/Word/Excel
8. OCR распознавание текста
9. Шаблонизатор документов
10. Личный кабинет
"""
import asyncio
import logging
import uuid
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
from models import init_db, SessionLocal, User, Subscription, Payment, Base, engine
from database import get_or_create_user, get_active_subscription, create_payment
from keyboards import main_menu_keyboard, subscription_keyboard, payment_keyboard
from keyboards_v2 import (
    main_menu_v2_keyboard, subscription_menu_keyboard, trial_keyboard,
    documents_keyboard, ocr_keyboard, review_rating_keyboard,
    review_category_keyboard, account_keyboard, ai_assistant_keyboard,
    back_to_menu_keyboard
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
        "💎 <b>Подписки:</b> оформление, смена тарифа, триал\n"
        "📄 <b>Документы:</b> конвертация PDF/Word/Excel\n"
        "🔍 <b>OCR:</b> распознавание текста с фото\n"
        "🤖 <b>AI-ассистент:</b> ответы на вопросы 24/7\n"
        "⭐ <b>Отзывы:</b> оценка и предложения\n"
        "👤 <b>Личный кабинет:</b> статистика, история\n"
        "👥 <b>Рефералы:</b> приглашайте друзей\n"
        "💬 <b>Поддержка:</b> связь с командой\n\n"
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
        "/changeplan - Сменить тариф\n"
        "/documents - Работа с документами\n"
        "/ocr - Распознавание текста\n"
        "/review - Оставить отзыв\n"
        "/referral - Реферальная программа\n"
        "/ai - AI-ассистент\n"
        "/support - Поддержка\n"
        "/status - Статус подписки\n"
        "/promo - Ввести промокод\n"
        "/help - Эта справка\n\n"
        "💡 Совет: используйте кнопки меню для быстрого доступа!"
    )
    await message.answer(help_text, parse_mode="HTML")


# ============= ТРИАЛ-ПЕРИОДЫ =============

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
                "🎁 <b>Триал-период завершен</b>\n\n"
                "Оформите платную подписку командой /subscribe"
            )
    else:
        text = (
            "🎁 <b>Триал-период</b>\n\n"
            "Попробуйте все возможности сервиса бесплатно!\n\n"
            "✨ <b>Что доступно:</b>\n"
            "• Все функции сервиса\n"
            "• Конвертация документов\n"
            "• OCR распознавание\n"
            "• Поддержка 24/7\n\n"
            "⏱ <b>Длительность:</b> 7 дней\n"
            "💳 <b>Оплата:</b> не требуется"
        )
    
    await message.answer(
        text, parse_mode="HTML",
        reply_markup=trial_keyboard()
    )


@dp.callback_query(F.data == "activate_trial")
async def process_activate_trial(callback_query: CallbackQuery):
    """Активация триала"""
    db = SessionLocal()
    try:
        user = get_or_create_user(db, callback_query.from_user.id)
        success, msg = start_trial(user.id, days=7)
    finally:
        db.close()
    
    await callback_query.message.edit_text(
        msg, parse_mode="HTML",
        reply_markup=back_to_menu_keyboard()
    )
    await callback_query.answer()


# ============= АПГРЕЙД/ДАУНГРЕЙД ТАРИФОВ =============

@dp.message(Command("changeplan"))
async def cmd_change_plan(message: Message):
    """Смена тарифа"""
    db = SessionLocal()
    try:
        user = get_or_create_user(db, message.from_user.id)
        current = get_current_plan(user.id)
        plans = get_all_plans()
    finally:
        db.close()
    
    if not current["plan"]:
        await message.answer(
            "❌ У вас нет активной подписки\n\n"
            "Оформите подписку командой /subscribe",
            reply_markup=back_to_menu_keyboard()
        )
        return
    
    text = (
        f"🔄 <b>Смена тарифа</b>\n\n"
        f"📦 <b>Текущий тариф:</b> {current['plan']}\n"
        f"⏳ <b>Осталось дней:</b> {current['days_left']}\n\n"
        f"<b>Доступные тарифы:</b>\n\n"
    )
    
    keyboard_buttons = []
    for plan in plans:
        if plan.name != current["plan"]:
            action = "🔼" if plan.level > current["level"] else "🔽"
            text += f"{action} <b>{plan.name}</b> - {plan.price/100:.0f}₽\n"
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{action} {plan.name}",
                    callback_data=f"change_to_{plan.name}"
                )
            ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")
    ])
    
    await message.answer(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )


@dp.callback_query(F.data.startswith("change_to_"))
async def process_change_plan(callback_query: CallbackQuery):
    """Обработка смены тарифа"""
    new_plan = callback_query.data.replace("change_to_", "")
    
    db = SessionLocal()
    try:
        user = get_or_create_user(db, callback_query.from_user.id)
        success, msg = upgrade_subscription(user.id, new_plan)
    finally:
        db.close()
    
    await callback_query.message.edit_text(
        msg, parse_mode="HTML",
        reply_markup=back_to_menu_keyboard()
    )
    await callback_query.answer()


# ============= AI-АССИСТЕНТ =============

@dp.message(Command("ai"))
async def cmd_ai(message: Message, state: FSMContext):
    """AI-ассистент"""
    await state.clear()
    
    text = (
        "🤖 <b>AI-ассистент</b>\n\n"
        "Задайте любой вопрос о нашем сервисе!\n\n"
        "💡 <b>Популярные темы:</b>\n"
        "• Подписка и оплата\n"
        "• Тарифы и триал\n"
        "• Конвертация документов\n"
        "• OCR распознавание\n"
        "• Реферальная программа\n\n"
        "Или выберите тему ниже:"
    )
    
    await message.answer(
        text, parse_mode="HTML",
        reply_markup=ai_assistant_keyboard()
    )


@dp.callback_query(F.data == "menu_ai")
async def process_menu_ai(callback_query: CallbackQuery, state: FSMContext):
    """AI из меню"""
    await cmd_ai(callback_query.message, state)
    await callback_query.answer()


@dp.callback_query(F.data == "ai_features")
async def process_ai_features(callback_query: CallbackQuery):
    """Возможности сервиса"""
    await callback_query.message.edit_text(
        get_product_consultation("возможности"),
        parse_mode="HTML",
        reply_markup=ai_assistant_keyboard()
    )
    await callback_query.answer()


@dp.callback_query(F.data == "ai_advantages")
async def process_ai_advantages(callback_query: CallbackQuery):
    """Преимущества"""
    await callback_query.message.edit_text(
        get_product_consultation("преимущества"),
        parse_mode="HTML",
        reply_markup=ai_assistant_keyboard()
    )
    await callback_query.answer()


@dp.callback_query(F.data == "ai_custom_question")
async def process_ai_custom(callback_query: CallbackQuery, state: FSMContext):
    """Задать свой вопрос"""
    await state.set_state(AIStates.waiting_for_question)
    await callback_query.message.edit_text(
        "💭 Напишите ваш вопрос:",
        reply_markup=back_to_menu_keyboard()
    )
    await callback_query.answer()


@dp.message(AIStates.waiting_for_question)
async def process_ai_question(message: Message, state: FSMContext):
    """Обработка вопроса"""
    answer = get_ai_response(message.text)
    await message.answer(
        f"🤖 <b>Ответ:</b>\n\n{answer}",
        parse_mode="HTML",
        reply_markup=ai_assistant_keyboard()
    )
    await state.clear()


# ============= ОТЗЫВЫ И РЕЙТИНГИ =============

@dp.message(Command("review"))
async def cmd_review(message: Message, state: FSMContext):
    """Оставить отзыв"""
    await state.clear()
    await state.set_state(ReviewStates.waiting_for_rating)
    
    text = (
        "⭐ <b>Оставить отзыв</b>\n\n"
        "Оцените наш сервис от 1 до 5 звёзд:"
    )
    
    await message.answer(
        text, parse_mode="HTML",
        reply_markup=review_rating_keyboard()
    )


@dp.callback_query(F.data.startswith("rate_"))
async def process_rating(callback_query: CallbackQuery, state: FSMContext):
    """Обработка рейтинга"""
    rating = int(callback_query.data.split("_")[1])
    await state.update_data(rating=rating)
    await state.set_state(ReviewStates.waiting_for_text)
    
    await callback_query.message.edit_text(
        f"⭐ Вы поставили: {'⭐' * rating}\n\n"
        "Напишите отзыв (или отправьте /skip чтобы пропустить):",
        parse_mode="HTML"
    )
    await callback_query.answer()


@dp.message(ReviewStates.waiting_for_text, F.text == "/skip")
async def skip_review_text(message: Message, state: FSMContext):
    """Пропустить текст отзыва"""
    await state.set_state(ReviewStates.waiting_for_suggestion)
    await message.answer(
        "💡 Есть предложения по улучшению? (или /skip)",
        reply_markup=back_to_menu_keyboard()
    )


@dp.message(ReviewStates.waiting_for_text)
async def process_review_text(message: Message, state: FSMContext):
    """Обработка текста отзыва"""
    await state.update_data(text=message.text)
    await state.set_state(ReviewStates.waiting_for_suggestion)
    await message.answer(
        "💡 Есть предложения по улучшению? (или /skip)",
        reply_markup=back_to_menu_keyboard()
    )


@dp.message(ReviewStates.waiting_for_suggestion, F.text == "/skip")
async def skip_suggestion(message: Message, state: FSMContext):
    """Пропустить предложение"""
    await finish_review(message, state, None)


@dp.message(ReviewStates.waiting_for_suggestion)
async def process_suggestion(message: Message, state: FSMContext):
    """Обработка предложения"""
    await finish_review(message, state, message.text)


async def finish_review(message: Message, state: FSMContext, suggestion):
    """Завершить создание отзыва"""
    data = await state.get_data()
    
    db = SessionLocal()
    try:
        user = get_or_create_user(db, message.from_user.id)
        review_id = create_review(
            user_id=user.id,
            rating=data["rating"],
            text=data.get("text"),
            suggestion=suggestion
        )
    finally:
        db.close()
    
    await state.clear()
    
    # Уведомляем админа
    for admin_id in settings.admin_ids_list:
        try:
            stars = "⭐" * data["rating"]
            await bot.send_message(
                admin_id,
                f"⭐ <b>Новый отзыв #{review_id}</b>\n\n"
                f"Рейтинг: {stars}\n"
                f"👤 От: @{message.from_user.username or message.from_user.id}\n"
                f"💬 Текст: {data.get('text', '—')}\n"
                f"💡 Предложение: {suggestion or '—'}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error notifying admin: {e}")
    
    await message.answer(
        "✅ <b>Спасибо за отзыв!</b>\n\n"
        "Ваше мнение очень важно для нас!",
        parse_mode="HTML",
        reply_markup=back_to_menu_keyboard()
    )


# ============= ДОКУМЕНТЫ =============

@dp.message(Command("documents"))
async def cmd_documents(message: Message, state: FSMContext):
    """Работа с документами"""
    await state.clear()
    
    text = (
        "📄 <b>Работа с документами</b>\n\n"
        "Выберите операцию:\n\n"
        "• <b>PDF → Текст:</b> извлечь текст из PDF\n"
        "• <b>Текст → PDF:</b> создать PDF из текста\n"
        "• <b>Шаблоны:</b> документы по шаблонам"
    )
    
    await message.answer(
        text, parse_mode="HTML",
        reply_markup=documents_keyboard()
    )


@dp.callback_query(F.data == "doc_pdf_to_txt")
async def process_pdf_to_txt(callback_query: CallbackQuery, state: FSMContext):
    """PDF в текст"""
    await state.set_state(DocumentStates.waiting_for_file)
    await state.update_data(operation="pdf_to_txt")
    
    await callback_query.message.edit_text(
        "📄 <b>PDF → Текст</b>\n\n"
        "Отправьте PDF-файл для извлечения текста:",
        parse_mode="HTML"
    )
    await callback_query.answer()


@dp.callback_query(F.data == "doc_txt_to_pdf")
async def process_txt_to_pdf(callback_query: CallbackQuery, state: FSMContext):
    """Текст в PDF"""
    await state.set_state(DocumentStates.waiting_for_file)
    await state.update_data(operation="txt_to_pdf")
    
    await callback_query.message.edit_text(
        "📝 <b>Текст → PDF</b>\n\n"
        "Отправьте текстовый файл для конвертации в PDF:",
        parse_mode="HTML"
    )
    await callback_query.answer()


@dp.message(DocumentStates.waiting_for_file, F.document)
async def process_document_upload(message: Message, state: FSMContext):
    """Обработка загруженного файла"""
    data = await state.get_data()
    operation = data.get("operation")
    
    document = message.document
    file_name = document.file_name
    file_ext = get_file_extension(file_name)
    
    # Скачиваем файл
    file = await bot.get_file(document.file_id)
    file_bytes = await bot.download_file(file.file_path)
    file_content = file_bytes.read()
    
    file_path = save_uploaded_file(file_content, file_ext)
    
    await message.answer("⏳ Обрабатываю файл...")
    
    if operation == "pdf_to_txt":
        success, msg, text = convert_pdf_to_text(file_path)
        
        if success:
            # Сохраняем результат
            result_path = file_path.replace(f".{file_ext}", "_text.txt")
            with open(result_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            # Отправляем результат
            if len(text) > 4000:
                await message.answer_document(
                    document=result_path,
                    caption="✅ Текст извлечен из PDF"
                )
            else:
                await message.answer(
                    f"✅ <b>Текст извлечен:</b>\n\n{text}",
                    parse_mode="HTML"
                )
        else:
            await message.answer(msg)
    
    elif operation == "txt_to_pdf":
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            success, msg, result_path = convert_text_to_pdf(text)
            
            if success:
                await message.answer_document(
                    document=result_path,
                    caption="✅ PDF создан"
                )
            else:
                await message.answer(msg)
        except Exception as e:
            await message.answer(f"❌ Ошибка: {str(e)}")
    
    await state.clear()


# ============= OCR =============

@dp.message(Command("ocr"))
async def cmd_ocr(message: Message, state: FSMContext):
    """OCR распознавание"""
    await state.clear()
    await state.set_state(DocumentStates.waiting_for_file)
    await state.update_data(operation="ocr")
    
    text = (
        "🔍 <b>OCR - Распознавание текста</b>\n\n"
        "Отправьте фото с текстом для распознавания.\n\n"
        "💡 <b>Советы:</b>\n"
        "• Используйте четкие изображения\n"
        "• Хорошее освещение улучшает результат\n"
        "• Поддерживаются русский и английский языки"
    )
    
    await message.answer(
        text, parse_mode="HTML",
        reply_markup=back_to_menu_keyboard()
    )


@dp.message(DocumentStates.waiting_for_file, F.photo)
async def process_photo_ocr(message: Message, state: FSMContext):
    """Обработка фото для OCR"""
    data = await state.get_data()
    if data.get("operation") != "ocr":
        return
    
    photo = message.photo[-1]  # Берем самое большое фото
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    file_content = file_bytes.read()
    
    file_path = save_uploaded_file(file_content, "jpg")
    
    await message.answer("⏳ Распознаю текст...")
    
    success, msg, text = ocr_from_image(file_path)
    
    if success:
        # Сохраняем результат
        result_path = file_path.replace(".jpg", "_ocr.txt")
        with open(result_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        if len(text) > 4000:
            await message.answer_document(
                document=result_path,
                caption="✅ Текст распознан"
            )
        else:
            await message.answer(
                f"✅ <b>Распознанный текст:</b>\n\n{text}",
                parse_mode="HTML"
            )
        
        # Обновляем статистику
        db = SessionLocal()
        try:
            user = get_or_create_user(db, message.from_user.id)
            update_stats(user.id, ocr_processed=1)
        finally:
            db.close()
    else:
        await message.answer(msg)
    
    await state.clear()


# ============= ЛИЧНЫЙ КАБИНЕТ =============

@dp.message(Command("account"))
async def cmd_account(message: Message):
    """Личный кабинет"""
    db = SessionLocal()
    try:
        user = get_or_create_user(db, message.from_user.id)
        info = get_account_info(user.id)
        payments = get_payment_history(user.id)
    finally:
        db.close()
    
    text = format_account_info(info)
    
    await message.answer(
        text, parse_mode="HTML",
        reply_markup=account_keyboard()
    )


@dp.callback_query(F.data == "account_payments")
async def process_account_payments(callback_query: CallbackQuery):
    """История платежей"""
    db = SessionLocal()
    try:
        user = get_or_create_user(db, callback_query.from_user.id)
        payments = get_payment_history(user.id)
    finally:
        db.close()
    
    text = format_payment_history(payments)
    
    await callback_query.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=account_keyboard()
    )
    await callback_query.answer()


# ============= PUSH-УВЕДОМЛЕНИЯ (АДМИН) =============

@dp.message(Command("news"))
async def cmd_news(message: Message, state: FSMContext):
    """Создание новости (для админов)"""
    if message.from_user.id not in settings.admin_ids_list:
        await message.answer("⛔ У вас нет доступа")
        return
    
    await state.set_state(NewsStates.waiting_for_title)
    await message.answer("📰 <b>Создание новости</b>\n\nВведите заголовок:", parse_mode="HTML")


@dp.message(NewsStates.waiting_for_title)
async def process_news_title(message: Message, state: FSMContext):
    """Заголовок новости"""
    await state.update_data(title=message.text)
    await state.set_state(NewsStates.waiting_for_content)
    await message.answer("Введите текст новости:")


@dp.message(NewsStates.waiting_for_content)
async def process_news_content(message: Message, state: FSMContext):
    """Текст новости и рассылка"""
    data = await state.get_data()
    
    news_id = create_news(
        title=data["title"],
        content=message.text,
        urgent=False,
        created_by=message.from_user.id
    )
    
    await message.answer(
        f"✅ Новость создана (#{news_id})\n\n"
        f"📤 Начать рассылку всем пользователям?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Да, разослать", callback_data=f"broadcast_{news_id}")],
            [InlineKeyboardButton(text="❌ Нет", callback_data="cancel_broadcast")]
        ])
    )
    await state.clear()


@dp.callback_query(F.data.startswith("broadcast_"))
async def process_broadcast(callback_query: CallbackQuery):
    """Рассылка новости"""
    news_id = int(callback_query.data.split("_")[1])
    
    await callback_query.message.edit_text("⏳ Начинаю рассылку...")
    
    sent, failed = await broadcast_news(bot, news_id)
    
    await callback_query.message.edit_text(
        f"✅ Рассылка завершена!\n\n"
        f"📤 Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}"
    )
    await callback_query.answer()


# ============= НАВИГАЦИЯ =============

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback_query: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    await callback_query.message.edit_text(
        "🏠 <b>Главное меню</b>\n\nВыберите раздел:",
        parse_mode="HTML",
        reply_markup=main_menu_v2_keyboard()
    )
    await callback_query.answer()


@dp.callback_query(F.data == "menu_subscription")
async def menu_subscription(callback_query: CallbackQuery):
    """Меню подписки"""
    await callback_query.message.edit_text(
        "💎 <b>Подписка</b>\n\nУправление подпиской:",
        parse_mode="HTML",
        reply_markup=subscription_menu_keyboard()
    )
    await callback_query.answer()


@dp.callback_query(F.data == "menu_trial")
async def menu_trial(callback_query: CallbackQuery):
    """Меню триала"""
    await cmd_trial(callback_query.message)
    await callback_query.answer()


@dp.callback_query(F.data == "menu_documents")
async def menu_documents(callback_query: CallbackQuery, state: FSMContext):
    """Меню документов"""
    await cmd_documents(callback_query.message, state)
    await callback_query.answer()


@dp.callback_query(F.data == "menu_ocr")
async def menu_ocr(callback_query: CallbackQuery, state: FSMContext):
    """Меню OCR"""
    await cmd_ocr(callback_query.message, state)
    await callback_query.answer()


@dp.callback_query(F.data == "menu_account")
async def menu_account(callback_query: CallbackQuery):
    """Личный кабинет из меню"""
    await cmd_account(callback_query.message)
    await callback_query.answer()


@dp.callback_query(F.data == "menu_reviews")
async def menu_reviews(callback_query: CallbackQuery, state: FSMContext):
    """Меню отзывов"""
    await cmd_review(callback_query.message, state)
    await callback_query.answer()


@dp.callback_query(F.data == "go_to_referral")
async def go_to_referral(callback_query: CallbackQuery):
    """Переход к рефералам"""
    from bot_extended import cmd_referral
    await cmd_referral(callback_query.message)
    await callback_query.answer()


@dp.callback_query(F.data == "go_to_support")
async def go_to_support(callback_query: CallbackQuery, state: FSMContext):
    """Переход к поддержке"""
    from bot_extended import cmd_support
    await cmd_support(callback_query.message, state)
    await callback_query.answer()


@dp.callback_query(F.data == "go_to_subscribe")
async def go_to_subscribe(callback_query: CallbackQuery, state: FSMContext):
    """Переход к оформлению подписки"""
    from bot_extended import cmd_subscribe
    await cmd_subscribe(callback_query.message, state)
    await callback_query.answer()


@dp.callback_query(F.data == "check_subscription")
async def check_subscription(callback_query: CallbackQuery):
    """Проверка подписки"""
    from bot_extended import cmd_status
    await cmd_status(callback_query.message)
    await callback_query.answer()


@dp.callback_query(F.data == "change_plan")
async def change_plan_callback(callback_query: CallbackQuery):
    """Смена тарифа из меню"""
    await cmd_change_plan(callback_query.message)
    await callback_query.answer()


# ============= MAIN =============

async def main():
    """Main function"""
    # Initialize database
    init_db()
    
    # Create extended tables
    from models_extended import PromoCode, PromoCodeUsage, Referral, SupportTicket
    Base.metadata.create_all(bind=engine)
    
    logger.info("✅ Database initialized")
    logger.info("🚀 Starting bot v2 with all features...")
    
    # Start notification scheduler
    asyncio.create_task(notification_scheduler())
    
    # Start polling
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
