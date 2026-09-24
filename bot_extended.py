"""
Extended Telegram Bot with all features
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
from models import init_db, SessionLocal, User, Subscription, Payment
from database import get_or_create_user, get_active_subscription, create_payment, complete_payment
from keyboards import main_menu_keyboard, subscription_keyboard, payment_keyboard
from keyboards_extended import (
    referral_keyboard, support_keyboard, promo_code_keyboard,
    admin_support_keyboard, subscription_with_promo_keyboard
)
from models_extended import PromoCode, Referral, SupportTicket
from promo_codes import validate_promo_code, use_promo_code, create_promo_code, get_all_promo_codes
from referrals import get_or_create_referral_code, register_referral, get_user_referrals
from support import create_support_ticket, get_user_tickets, get_all_open_tickets, respond_to_ticket, close_ticket
from notifications import notification_scheduler

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


class AdminStates(StatesGroup):
    waiting_for_promo_code = State()
    waiting_for_promo_discount = State()
    waiting_for_promo_uses = State()


# ============= COMMAND HANDLERS =============

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command with referral support"""
    await state.clear()
    
    # Проверяем реферальный код
    args = message.text.split()
    referrer_id = None
    
    if len(args) > 1 and args[1].startswith("ref_"):
        referral_code = args[1][4:]
        # Здесь можно обработать реферальный код
        # register_referral(referrer_id, message.from_user.id)
    
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
        "• 💎 Оформление подписки с оплатой через СБП\n"
        "• 🎁 Промокоды и скидки\n"
        "• 👥 Реферальная программа\n"
        "• 💬 Поддержка 24/7\n"
        "• 📊 Проверка статуса подписки\n\n"
        "Выберите действие:"
    )
    
    await message.answer(
        welcome_text,
        parse_mode="HTML",
        reply_markup=subscription_with_promo_keyboard()
    )


@dp.message(Command("referral"))
async def cmd_referral(message: Message):
    """Show referral program"""
    db = SessionLocal()
    try:
        user = get_or_create_user(
            db,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
        
        referral_code = get_or_create_referral_code(user.id)
        referrals = get_user_referrals(user.id)
    finally:
        db.close()
    
    referral_link = f"https://t.me/{(await bot.get_me()).username}?start=ref_{referral_code}"
    
    text = (
        f"👥 <b>Реферальная программа</b>\n\n"
        f"Приглашайте друзей и получайте бонусы!\n\n"
        f"🎁 <b>Ваши бонусы:</b>\n"
        f"• +7 дней подписки за каждого друга\n"
        f"• Друг получает скидку 10% на первую оплату\n\n"
        f"📊 <b>Ваша статистика:</b>\n"
        f"• Приглашено: {len(referrals)}\n"
        f"• Активировано: {sum(1 for r in referrals if r.activated)}\n\n"
        f"🔗 <b>Ваша ссылка:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        f"Поделитесь ссылкой с друзьями!"
    )
    
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=referral_keyboard(referral_code, (await bot.get_me()).username)
    )


@dp.message(Command("support"))
async def cmd_support(message: Message, state: FSMContext):
    """Show support menu"""
    await state.clear()
    
    text = (
        "💬 <b>Поддержка</b>\n\n"
        "Нужна помощь? Мы здесь!\n\n"
        "• Ответим на ваши вопросы\n"
        "• Поможем с оплатой\n"
        "• Решим технические проблемы\n"
        "• Время ответа: до 2 часов\n\n"
        "Выберите действие:"
    )
    
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=support_keyboard()
    )


@dp.message(Command("promo"))
async def cmd_promo(message: Message, state: FSMContext):
    """Enter promo code"""
    await state.set_state(SubscriptionStates.waiting_for_promo_code)
    
    text = (
        "🎁 <b>Ввод промокода</b>\n\n"
        "Введите ваш промокод:\n\n"
        "Пример: <code>WELCOME20</code>"
    )
    
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=promo_code_keyboard()
    )


# ============= CALLBACK HANDLERS =============

@dp.callback_query(F.data == "enter_promo_code")
async def process_enter_promo(callback_query: CallbackQuery, state: FSMContext):
    """Process enter promo code"""
    await state.set_state(SubscriptionStates.waiting_for_promo_code)
    
    text = (
        "🎁 <b>Ввод промокода</b>\n\n"
        "Введите ваш промокод:\n\n"
        "Пример: <code>WELCOME20</code>"
    )
    
    await callback_query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=promo_code_keyboard()
    )
    await callback_query.answer()


@dp.message(SubscriptionStates.waiting_for_promo_code)
async def process_promo_code_input(message: Message, state: FSMContext):
    """Process promo code input"""
    promo_code = message.text.strip().upper()
    
    db = SessionLocal()
    try:
        user = get_or_create_user(
            db,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
        
        is_valid, msg, promo = validate_promo_code(promo_code, user.id)
    finally:
        db.close()
    
    if is_valid:
        await state.update_data(promo_code=promo_code, discount=promo.discount_percent)
        
        text = (
            f"{msg}\n\n"
            f"💰 <b>Скидка:</b> {promo.discount_percent}%\n"
            f"📦 <b>Осталось использований:</b> {promo.max_uses - promo.used_count}\n\n"
            f"Скидка будет применена при оформлении подписки.\n"
            f"Используйте команду /subscribe"
        )
        
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=subscription_with_promo_keyboard()
        )
    else:
        await message.answer(
            msg,
            reply_markup=subscription_with_promo_keyboard()
        )
    
    await state.clear()


@dp.callback_query(F.data == "cancel_promo")
async def cancel_promo(callback_query: CallbackQuery, state: FSMContext):
    """Cancel promo code input"""
    await state.clear()
    await callback_query.message.edit_text(
        "❌ Ввод промокода отменен",
        reply_markup=subscription_with_promo_keyboard()
    )
    await callback_query.answer()


@dp.callback_query(F.data == "create_ticket")
async def process_create_ticket(callback_query: CallbackQuery, state: FSMContext):
    """Process create support ticket"""
    await state.set_state(SupportStates.waiting_for_message)
    
    text = (
        "✍️ <b>Написать в поддержку</b>\n\n"
        "Опишите вашу проблему или вопрос:\n\n"
        "Мы ответим в течение 2 часов."
    )
    
    await callback_query.message.edit_text(
        text,
        parse_mode="HTML"
    )
    await callback_query.answer()


@dp.message(SupportStates.waiting_for_message)
async def process_support_message(message: Message, state: FSMContext):
    """Process support message"""
    db = SessionLocal()
    try:
        user = get_or_create_user(
            db,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
        
        ticket_id = create_support_ticket(user.id, message.text)
    finally:
        db.close()
    
    await state.clear()
    
    # Уведомляем админа
    for admin_id in settings.admin_ids_list:
        try:
            await bot.send_message(
                admin_id,
                f"🎫 <b>Новое обращение #{ticket_id}</b>\n\n"
                f"👤 От: @{message.from_user.username or message.from_user.id}\n"
                f"💬 Сообщение: {message.text}",
                parse_mode="HTML",
                reply_markup=admin_support_keyboard(ticket_id)
            )
        except Exception as e:
            logger.error(f"Error notifying admin {admin_id}: {e}")
    
    await message.answer(
        f"✅ Ваше обращение #{ticket_id} принято!\n\n"
        f"Мы ответим в течение 2 часов.",
        reply_markup=support_keyboard()
    )


@dp.callback_query(F.data == "my_tickets")
async def process_my_tickets(callback_query: CallbackQuery):
    """Process my tickets"""
    db = SessionLocal()
    try:
        user = get_or_create_user(
            db,
            callback_query.from_user.id,
            callback_query.from_user.username,
            callback_query.from_user.first_name,
            callback_query.from_user.last_name
        )
        
        tickets = get_user_tickets(user.id)
    finally:
        db.close()
    
    if not tickets:
        text = "📋 У вас нет обращений"
    else:
        text = "📋 <b>Ваши обращения:</b>\n\n"
        for ticket in tickets[:5]:  # Показываем последние 5
            status_emoji = {
                "open": "🟢",
                "in_progress": "🟡",
                "closed": "✅"
            }.get(ticket.status, "⚪")
            
            text += (
                f"{status_emoji} <b>#{ticket.id}</b> - {ticket.status}\n"
                f"📅 {ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"💬 {ticket.message[:50]}...\n\n"
            )
    
    await callback_query.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=support_keyboard()
    )
    await callback_query.answer()


@dp.callback_query(F.data.startswith("respond_ticket_"))
async def process_respond_ticket(callback_query: CallbackQuery, state: FSMContext):
    """Process respond to ticket"""
    ticket_id = int(callback_query.data.split("_")[2])
    
    if callback_query.from_user.id not in settings.admin_ids_list:
        await callback_query.answer("⛔ У вас нет доступа", show_alert=True)
        return
    
    await state.update_data(ticket_id=ticket_id)
    await state.set_state(SupportStates.waiting_for_response)
    
    await callback_query.message.edit_text(
        f"✍️ Введите ответ на обращение #{ticket_id}:"
    )
    await callback_query.answer()


@dp.message(SupportStates.waiting_for_response)
async def process_admin_response(message: Message, state: FSMContext):
    """Process admin response"""
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    
    if respond_to_ticket(ticket_id, message.text):
        db = SessionLocal()
        try:
            ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
            user = db.query(User).filter(User.id == ticket.user_id).first()
            
            if user:
                await bot.send_message(
                    user.telegram_id,
                    f"💬 <b>Ответ на обращение #{ticket_id}</b>\n\n"
                    f"{message.text}",
                    parse_mode="HTML"
                )
        finally:
            db.close()
        
        await message.answer(f"✅ Ответ отправлен!")
    else:
        await message.answer(f"❌ Ошибка отправки ответа")
    
    await state.clear()


@dp.callback_query(F.data.startswith("close_ticket_"))
async def process_close_ticket(callback_query: CallbackQuery):
    """Process close ticket"""
    ticket_id = int(callback_query.data.split("_")[2])
    
    if callback_query.from_user.id not in settings.admin_ids_list:
        await callback_query.answer("⛔ У вас нет доступа", show_alert=True)
        return
    
    if close_ticket(ticket_id):
        await callback_query.message.edit_text(f"✅ Обращение #{ticket_id} закрыто")
    else:
        await callback_query.message.edit_text(f"❌ Ошибка закрытия обращения")
    
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
        "/users - Список пользователей\n"
        "/createpromo - Создать промокод\n"
        "/promos - Список промокодов\n"
        "/tickets - Открытые обращения"
    )
    
    await message.answer(admin_text, parse_mode="HTML")


@dp.message(Command("createpromo"))
async def cmd_create_promo(message: Message, state: FSMContext):
    """Create promo code"""
    if message.from_user.id not in settings.admin_ids_list:
        await message.answer("⛔ У вас нет доступа к этой команде")
        return
    
    await state.set_state(AdminStates.waiting_for_promo_code)
    await message.answer("🎁 Введите код промокода:")


@dp.message(AdminStates.waiting_for_promo_code)
async def process_promo_code(message: Message, state: FSMContext):
    """Process promo code creation"""
    await state.update_data(code=message.text.strip().upper())
    await state.set_state(AdminStates.waiting_for_promo_discount)
    await message.answer("💰 Введите размер скидки в процентах (например, 20):")


@dp.message(AdminStates.waiting_for_promo_discount)
async def process_promo_discount(message: Message, state: FSMContext):
    """Process promo discount"""
    try:
        discount = int(message.text.strip())
        if discount < 1 or discount > 100:
            raise ValueError
        
        await state.update_data(discount=discount)
        await state.set_state(AdminStates.waiting_for_promo_uses)
        await message.answer("🔢 Введите максимальное количество использований:")
    
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число от 1 до 100:")


@dp.message(AdminStates.waiting_for_promo_uses)
async def process_promo_uses(message: Message, state: FSMContext):
    """Process promo uses"""
    try:
        max_uses = int(message.text.strip())
        if max_uses < 1:
            raise ValueError
        
        data = await state.get_data()
        code = data.get("code")
        discount = data.get("discount")
        
        promo = create_promo_code(code, discount, max_uses)
        
        await message.answer(
            f"✅ Промокод создан!\n\n"
            f"🎁 <b>Код:</b> <code>{promo.code}</code>\n"
            f"💰 <b>Скидка:</b> {promo.discount_percent}%\n"
            f"🔢 <b>Использований:</b> {promo.max_uses}",
            parse_mode="HTML"
        )
        
        await state.clear()
    
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число больше 0:")
    
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
        await state.clear()


@dp.message(Command("promos"))
async def cmd_promos(message: Message):
    """List all promo codes"""
    if message.from_user.id not in settings.admin_ids_list:
        await message.answer("⛔ У вас нет доступа к этой команде")
        return
    
    promos = get_all_promo_codes()
    
    if not promos:
        await message.answer("📋 Промокоды не найдены")
        return
    
    text = "🎁 <b>Все промокоды:</b>\n\n"
    for promo in promos:
        status = "✅" if promo.is_valid else "❌"
        text += (
            f"{status} <code>{promo.code}</code>\n"
            f"💰 Скидка: {promo.discount_percent}%\n"
            f"🔢 Использовано: {promo.used_count}/{promo.max_uses}\n\n"
        )
    
    await message.answer(text, parse_mode="HTML")


@dp.message(Command("tickets"))
async def cmd_tickets(message: Message):
    """List open tickets"""
    if message.from_user.id not in settings.admin_ids_list:
        await message.answer("⛔ У вас нет доступа к этой команде")
        return
    
    tickets = get_all_open_tickets()
    
    if not tickets:
        await message.answer("📋 Нет открытых обращений")
        return
    
    text = "🎫 <b>Открытые обращения:</b>\n\n"
    for ticket in tickets[:10]:
        text += (
            f"🟢 <b>#{ticket.id}</b>\n"
            f"📅 {ticket.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"💬 {ticket.message[:50]}...\n\n"
        )
    
    await message.answer(text, parse_mode="HTML")


# ============= MAIN =============

async def main():
    """Main function"""
    # Initialize database
    init_db()
    
    # Create extended tables
    from models import Base, engine
    from models_extended import PromoCode, PromoCodeUsage, Referral, SupportTicket
    Base.metadata.create_all(bind=engine)
    
    logger.info("Starting bot with extended features...")
    
    # Start notification scheduler
    asyncio.create_task(notification_scheduler())
    
    # Start polling
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
