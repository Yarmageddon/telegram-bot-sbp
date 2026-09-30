from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from agents import get_agent_menu_items

def agents_menu() -> InlineKeyboardMarkup:
    """Клавиатура выбора агента."""
    items = get_agent_menu_items()
    keyboard = []
    for i in range(0, len(items), 2):
        row = []
        for cb_data, label in items[i:i+2]:
            row.append(InlineKeyboardButton(text=label, callback_data=cb_data))
        keyboard.append(row)
    keyboard.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="back:main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def agent_action_menu(agent_id: str) -> InlineKeyboardMarkup:
    """Меню действий внутри агента."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Задать вопрос", callback_data=f"agent_ask:{agent_id}")],
        [InlineKeyboardButton(text="🔄 Сменить агента", callback_data="agent:menu")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back:main")],
    ])
