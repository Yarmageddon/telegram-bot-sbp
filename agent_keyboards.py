"""
agent_keyboards.py — Клавиатуры для агентов.

Меню агента строится динамически из agent.menu_buttons.
Внизу всегда есть кнопка «🔙 Назад» → возврат к списку агентов.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from agents import get_available_agents, get_agent


# ═══════════════════════════════════════════════════════════════
# ГЛАВНОЕ МЕНЮ — ПЛОСКИЙ СПИСОК АГЕНТОВ
# ═══════════════════════════════════════════════════════════════

def agents_main_menu() -> InlineKeyboardMarkup:
    """Плоский список агентов по 2 в ряд."""
    agents = get_available_agents()
    rows = []

    for i in range(0, len(agents), 2):
        pair = agents[i:i + 2]
        rows.append([
            InlineKeyboardButton(
                text=f"{a.emoji} {a.name}",
                callback_data=f"agent:{a.id}",
            )
            for a in pair
        ])

    rows.append([
        InlineKeyboardButton(text="🔙 В главное меню", callback_data="back:main")
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# ═══════════════════════════════════════════════════════════════
# МЕНЮ АГЕНТА — КНОПКИ ИЗ agent.menu_buttons
# ═══════════════════════════════════════════════════════════════

def agent_menu(agent_id: str) -> InlineKeyboardMarkup:
    """Меню конкретного агента: его кнопки + Назад."""
    agent = get_agent(agent_id)
    if not agent:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Назад", callback_data="agents:menu"),
        ]])

    rows = []

    # Кнопки агента — по одной в ряд (длинные подписи)
    for idx, button in enumerate(agent.menu_buttons):
        rows.append([
            InlineKeyboardButton(
                text=button.label,
                callback_data=f"abtn:{agent_id}:{idx}",
            )
        ])

    # Навигация
    rows.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="agents:menu"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_agent_menu(agent_id: str) -> InlineKeyboardMarkup:
    """Клавиатура под ответом агента: «В меню агента» + «Список агентов»."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="↩️ Меню агента",
                callback_data=f"agent:{agent_id}",
            ),
            InlineKeyboardButton(
                text="🔙 К списку",
                callback_data="agents:menu",
            ),
        ],
    ])


# ═══════════════════════════════════════════════════════════════
# ПОДТВЕРЖДЕНИЕ ДЕЙСТВИЙ (для чек-листов, отметок)
# ═══════════════════════════════════════════════════════════════

def confirm_action_menu(agent_id: str, action: str,
                        payload: str = "") -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения действия.
    Пример: 'Кухня — готово' → confirm:cleaning:done:Кухня
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=f"confirm:{agent_id}:{action}:{payload}",
        )],
        [InlineKeyboardButton(
            text="🔙 Назад",
            callback_data=f"agent:{agent_id}",
        )],
    ])
