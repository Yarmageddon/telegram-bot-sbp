"""
Telegram Bot with SBP Payments - aiogram 3.x version
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import settings
from models import init_db, SessionLocal
from database import get_or_create_user, get_active_subscription, create_payment, complete_payment
from keyboards import main_menu_keyboard, subscription_keyboard, payment_keyboard

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


# ============= COMMAND HANDLERS =============

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Handle /start command"""
    db = SessionLocal()
    try:
        user = get_or_create_user(
            db,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
    finally:
        db.close()
    
    welcome_text = (
        "👋 <b>Добро пожаловать!</b>\n\n"
        "Я помогу вам оформить подписку и управлять ею.\n\n"
        "✨ <b>Возможности:</b>\n"
        "• Оформление подписки с оплатой через СБП\n"
        "• Проверка статуса подписки\n"
        "• Управление аккаунтом\n\n"
        "Выберите действие:"
    )
    
    await message.answer(
        welcome_text,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard()
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command"""
    help_text = (
        " <b>Помощь</b>\n\n"
        "<b>Доступные команды:</b>\n"
        "/start - Главное меню\n"
        "/status - Проверить статус подписки\n"
        "/subscribe - Оформить подписку\n"
        "/help - Показать это сообщение\n\n"
        "<b>Как оформить подписку:</b>\n"
        "1. Нажмите 'Оформить подписку'\n"
        "2. Выберите тарифный план\n"
        "3. Оплатите через СБП\n"
        "4. Подписка активируется автоматически\n\n"
        "Если у вас возникли вопросы, обратитесь к администратору."
    )
    
    await message.answer(
        help_text,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard()
    )


@dp.message(Command("status"))
async def cmd_status(message: Message):
    """Handle /status command"""
    db = SessionLocal()
    try:
        user = get_or_create_user(
            db,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
        
        subscription = get_active_subscription(db, user.id)
    finally:
        db.close()
    
    if subscription:
        days_left = (subscription.expires_at - datetime.now()).days
        status_text = (
            "✅ <b>Ваша подписка активна</b>\n\n"
            f"📅 <b>План:</b> {subscription.plan}\n"
            f" <b>Действует до:</b> {subscription.expires_at.strftime('%d.%m.%Y')}\n"
            f"⏳ <b>Осталось дней:</b> {days_left}\n\n"
            "Спасибо, что остаетесь с нами!"
        )
    else:
        status_text = (
            "❌ <b>У вас нет активной подписки</b>\n\n"
            "Оформите подписку, чтобы получить доступ ко всем возможностям сервиса."
        )
    
    await message.answer(
        status_text,
        parse_mode="HTML",
        reply_markup=subscription_keyboard()
    )


@dp.message(Command("subscribe"))
async def cmd_subscribe(message: Message, state: FSMContext):
    """Handle /subscribe command"""
    await state.clear()
    
    subscription_text = (
        "💎 <b>Оформление подписки</b>\n\n"
        "Выберите подходящий тарифный план:\n\n"
        "📦 <b>Месячная подписка</b>\n"
        "• 30 дней доступа\n"
        "• Все функции сервиса\n"
        "• Приоритетная поддержка\n"
        "💰 <b>990 ₽</b>\n\n"
        "📦 <b>Годовая подписка</b>\n"
        "• 365 дней доступа\n"
        "• Экономия 20%\n"
        "• Бонусные возможности\n"
        "💰 <b>9 500 ₽</b>\n\n"
        "Выберите план:"
    )
    
    await message.answer(
        subscription_text,
        parse_mode="HTML",
        reply_markup=payment_keyboard()
    )
    await SubscriptionStates.waiting_for_plan_selection.set()


# ============= CALLBACK HANDLERS =============

@dp.callback_query(F.data == "monthly_plan", SubscriptionStates.waiting_for_plan_selection)
async def process_monthly_plan(callback_query: CallbackQuery, state: FSMContext):
    """Process monthly plan selection"""
    await process_plan_selection(callback_query, state, "monthly", 99000, "Месячная подписка")


@dp.callback_query(F.data == "yearly_plan", SubscriptionStates.waiting_for_plan_selection)
async def process_yearly_plan(callback_query: CallbackQuery, state: FSMContext):
    """Process yearly plan selection"""
    await process_plan_selection(callback_query, state, "yearly", 950000, "Годовая подписка")


async def process_plan_selection(callback_query: CallbackQuery, state: FSMContext, 
                                  plan: str, amount: int, plan_name: str):
    """Process plan selection"""
    await state.update_data(plan=plan, amount=amount)
    
    # Create payment
    transaction_id = f"tx_{uuid.uuid4().hex[:16]}"
    payment_url = f"https://your-payment-provider.com/pay?user={callback_query.from_user.id}&amount={amount}&plan={plan}&tx={transaction_id}"
    
    # Save payment to database
    db = SessionLocal()
    try:
        user = get_or_create_user(db, callback_query.from_user.id)
        create_payment(
            db,
            user_id=user.id,
            provider_tx_id=transaction_id,
            amount=amount,
            currency="RUB",
            payload=f"{plan}:{plan_name}"
        )
    finally:
        db.close()
    
    payment_text = (
        f"💳 <b>Оплата подписки</b>\n\n"
        f"📦 <b>План:</b> {plan_name}\n"
        f"💰 <b>Сумма:</b> {amount / 100:.0f} ₽\n\n"
        "Для оплаты нажмите кнопку ниже:\n"
        "Вы будете перенаправлены на страницу оплаты СБП."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=" Оплатить через СБП", url=payment_url)],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_payment")]
    ])
    
    await callback_query.message.edit_text(
        payment_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await SubscriptionStates.waiting_for_payment_confirmation.set()
    await callback_query.answer()


@dp.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback_query: CallbackQuery, state: FSMContext):
    """Cancel payment"""
    await state.clear()
    await callback_query.message.edit_text(
        "❌ Оплата отменена\n\n"
        "Вы можете вернуться в главное меню.",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard()
    )
    await callback_query.answer()


@dp.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback_query: CallbackQuery):
    """Check subscription from inline keyboard"""
    db = SessionLocal()
    try:
        user = get_or_create_user(
            db,
            callback_query.from_user.id,
            callback_query.from_user.username,
            callback_query.from_user.first_name,
            callback_query.from_user.last_name
        )
        
        subscription = get_active_subscription(db, user.id)
    finally:
        db.close()
    
    if subscription:
        days_left = (subscription.expires_at - datetime.now()).days
        status_text = (
            "✅ <b>Ваша подписка активна</b>\n\n"
            f"📅 <b>План:</b> {subscription.plan}\n"
            f" <b>Действует до:</b> {subscription.expires_at.strftime('%d.%m.%Y')}\n"
            f"⏳ <b>Осталось дней:</b> {days_left}\n\n"
            "Спасибо, что остаетесь с нами!"
        )
    else:
        status_text = (
            "❌ <b>У вас нет активной подписки</b>\n\n"
            "Оформите подписку, чтобы получить доступ ко всем возможностям сервиса."
        )
    
    await callback_query.message.edit_text(
        status_text,
        parse_mode="HTML",
        reply_markup=subscription_keyboard()
    )
    await callback_query.answer()


@dp.callback_query(F.data == "go_to_subscribe")
async def go_to_subscribe_callback(callback_query: CallbackQuery, state: FSMContext):
    """Go to subscribe from inline keyboard"""
    await state.clear()
    await cmd_subscribe(callback_query.message, state)
    await callback_query.answer()


@dp.callback_query(F.data == "help")
async def help_callback(callback_query: CallbackQuery):
    """Help callback"""
    await cmd_help(callback_query.message)
    await callback_query.answer()


# ============= ADMIN COMMANDS =============

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    """Admin panel"""
    if message.from_user.id not in settings.admin_ids_list:
        await message.answer("⛔ У вас нет доступа к этой команде")
        return
    
    admin_text = (
        "🔧 <b>Панель администратора</b>\n\n"
        "Доступные команды:\n"
        "/stats - Статистика бота\n"
        "/users - Список пользователей"
    )
    
    await message.answer(admin_text, parse_mode="HTML")


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    """Show statistics"""
    if message.from_user.id not in settings.admin_ids_list:
        await message.answer("⛔ У вас нет доступа к этой команде")
        return
    
    db = SessionLocal()
    try:
        from models import User, Subscription, Payment
        total_users = db.query(User).count()
        active_subscriptions = db.query(Subscription).filter(
            Subscription.active == True,
            Subscription.expires_at > datetime.now()
        ).count()
        total_payments = db.query(Payment).filter(Payment.status == "completed").count()
    finally:
        db.close()
    
    stats_text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"• Всего: {total_users}\n\n"
        f"💳 <b>Подписки:</b>\n"
        f"• Активных: {active_subscriptions}\n\n"
        f"💰 <b>Платежи:</b>\n"
        f"• Успешных: {total_payments}"
    )
    
    await message.answer(stats_text, parse_mode="HTML")


# ============= MAIN =============

async def main():
    """Main function"""
    # Initialize database
    init_db()
    
    logger.info("Starting bot...")
    
    # Start polling
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
