"""
Extended keyboards for new features
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def referral_keyboard(referral_code: str, bot_username: str) -> InlineKeyboardMarkup:
    """Referral keyboard with share button"""
    share_url = f"https://t.me/{bot_username}?start=ref_{referral_code}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться ссылкой", switch_inline_query=share_url)],
        [InlineKeyboardButton(text="📋 Скопировать ссылку", callback_data=f"copy_referral_{referral_code}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    return keyboard


def support_keyboard() -> InlineKeyboardMarkup:
    """Support menu keyboard"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Написать в поддержку", callback_data="create_ticket")],
        [InlineKeyboardButton(text="📋 Мои обращения", callback_data="my_tickets")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    return keyboard


def promo_code_keyboard() -> InlineKeyboardMarkup:
    """Promo code input keyboard"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_promo")]
    ])
    return keyboard


def admin_support_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    """Admin keyboard for support ticket"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ответить", callback_data=f"respond_ticket_{ticket_id}")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data=f"close_ticket_{ticket_id}")]
    ])
    return keyboard


def subscription_with_promo_keyboard() -> InlineKeyboardMarkup:
    """Subscription menu with promo code option"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Оформить подписку", callback_data="go_to_subscribe")],
        [InlineKeyboardButton(text="🎁 Ввести промокод", callback_data="enter_promo_code")],
        [InlineKeyboardButton(text="📊 Проверить подписку", callback_data="check_subscription")],
        [InlineKeyboardButton(text="📚 Помощь", callback_data="help")]
    ])
    return keyboard
