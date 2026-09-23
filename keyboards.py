from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu keyboard"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Оформить подписку", callback_data="go_to_subscribe")],
        [InlineKeyboardButton(text="📊 Проверить подписку", callback_data="check_subscription")],
        [InlineKeyboardButton(text="📚 Помощь", callback_data="help")]
    ])
    return keyboard


def subscription_keyboard() -> InlineKeyboardMarkup:
    """Subscription menu keyboard"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Оформить подписку", callback_data="go_to_subscribe")],
        [InlineKeyboardButton(text="🔄 Обновить статус", callback_data="check_subscription")]
    ])
    return keyboard


def payment_keyboard() -> InlineKeyboardMarkup:
    """Payment plan selection keyboard"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Месячная подписка - 990 ₽", callback_data="monthly_plan")],
        [InlineKeyboardButton(text=" Годовая подписка - 9 500 ₽", callback_data="yearly_plan")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_payment")]
    ])
    return keyboard
