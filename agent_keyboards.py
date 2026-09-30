"""
agent_keyboards.py — Клавиатуры для навигации по агентам.

Структура меню:
1. Главное меню агентов: кнопки категорий + "Все агенты"
2. Меню категории: список агентов внутри категории
3. Меню агента: "Задать вопрос", "Сменить агента", "Назад"
4. Быстрые действия: кнопки-подсказки под конкретного агента
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from agents import (
    get_agents_by_category,
    get_categories,
    get_category_title,
    get_agent,
    get_available_agents,
)


# ═══════════════════════════════════════════════════════════════
# 1. ГЛАВНОЕ МЕНЮ АГЕНТОВ (список категорий)
# ═══════════════════════════════════════════════════════════════

def agents_main_menu() -> InlineKeyboardMarkup:
    """Главное меню: плоский список всех агентов по 2 в ряд."""
    agents = get_available_agents()
    rows = []

    # Пары по 2 кнопки в ряд
    for i in range(0, len(agents), 2):
        pair = agents[i:i + 2]
        rows.append([
            InlineKeyboardButton(
                text=f"{a.emoji} {a.name}",
                callback_data=f"agent:{a.id}",
            )
            for a in pair
        ])

    # Кнопка «Назад» в главное меню бота
    rows.append([
        InlineKeyboardButton(text="🔙 В главное меню", callback_data="back:main")
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# ═══════════════════════════════════════════════════════════════
# 2. МЕНЮ КАТЕГОРИИ (агенты внутри категории)
# ═══════════════════════════════════════════════════════════════

def category_menu(category: str) -> InlineKeyboardMarkup:
    """Меню конкретной категории: список агентов внутри."""
    rows = []
    agents_in_cat = get_agents_by_category(category)

    for agent in agents_in_cat:
        rows.append([
            InlineKeyboardButton(
                text=f"{agent.emoji} {agent.name} — {agent.description}",
                callback_data=f"agent:{agent.id}",
            )
        ])

    # Навигация
    rows.append([
        InlineKeyboardButton(text="🔙 К категориям", callback_data="agents:menu"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def all_agents_menu() -> InlineKeyboardMarkup:
    """Плоский список всех агентов (когда нажали «Все агенты»)."""
    rows = []
    for agent in get_available_agents():
        rows.append([
            InlineKeyboardButton(
                text=f"{agent.emoji} {agent.name}",
                callback_data=f"agent:{agent.id}",
            )
        ])
    rows.append([
        InlineKeyboardButton(text="🔙 К категориям", callback_data="agents:menu"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ═══════════════════════════════════════════════════════════════
# 3. МЕНЮ АГЕНТА (когда выбрали конкретного)
# ═══════════════════════════════════════════════════════════════

def agent_action_menu(agent_id: str) -> InlineKeyboardMarkup:
    """Меню внутри агента."""
    rows = [
        [
            InlineKeyboardButton(
                text="💬 Задать вопрос",
                callback_data=f"agent_ask:{agent_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="🔄 Сменить агента",
                callback_data="agents:menu",
            )
        ],
        [
            InlineKeyboardButton(
                text="🗑 Очистить историю",
                callback_data=f"agent_clear:{agent_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="🔙 В главное меню",
                callback_data="back:main",
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def agent_chat_keyboard(agent_id: str) -> InlineKeyboardMarkup:
    """Клавиатура под сообщениями в режиме чата с агентом."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔄 Сменить агента",
                callback_data="agents:menu",
            ),
            InlineKeyboardButton(
                text="🗑 Очистить",
                callback_data=f"agent_clear:{agent_id}",
            ),
        ],
    ])


# ═══════════════════════════════════════════════════════════════
# 4. БЫСТРЫЕ ПОДСКАЗКИ (под конкретного агента)
# ═══════════════════════════════════════════════════════════════

# Готовые примеры запросов для каждого агента.
# Показываются как кнопки после выбора агента — чтобы пользователь
# сразу понял, что можно спросить.
AGENT_QUICK_PROMPTS: dict[str, list[str]] = {
    "reminder": [
        "Напомни завтра в 10:00 позвонить маме",
        "Какие у меня напоминания?",
    ],
    "task_manager": [
        "Добавь задачу: подготовить отчёт к пятнице",
        "Покажи мои задачи",
        "Что у меня в работе?",
    ],
    "daily_planner": [
        "Собери план на сегодня",
        "Что у меня по расписанию?",
    ],
    "subscription": [
        "Покажи все мои подписки",
        "Сколько я трачу на подписки в месяц?",
    ],
    "cleaning": [
        "Что мне убрать сегодня?",
        "Составь график уборки на неделю",
    ],
    "family": [
        "Что кому поручено по дому?",
        "Добавь семейную задачу",
    ],
    "weather": [
        "Какая погода в Москве?",
        "Прогноз на завтра",
        "Будет ли дождь?",
    ],
    "calendar_birthday": [
        "Что у меня сегодня в календаре?",
        "Чьи дни рождения на этой неделе?",
    ],
    "email_triage": [
        "Разбери мою почту",
        "Есть срочные письма?",
    ],
    "nutrition": [
        "Сколько я выпил воды сегодня?",
        "Запиши: съел салат на обед",
        "Сводка по питанию",
    ],
    "mental_health": [
        "Хочу записать настроение",
        "Предложи практику от тревоги",
        "Как я себя чувствовал на неделе?",
    ],
    "lawyer": [
        "Разбери мой договор",
        "Помоги с претензией",
        "Какие сроки по делу?",
    ],
    "analyst": [
        "Проанализируй данные по продажам",
        "Найди аномалии в метриках",
        "Построй отчёт",
    ],
    "translator": [
        "Переведи на английский: Привет, как дела?",
        "Что значит идиома 'break a leg'?",
    ],
    "copywriter": [
        "Напиши пост для Telegram о продукте",
        "Придумай 3 заголовка для статьи",
    ],
    "garden": [
        "Что полить сегодня?",
        "Добавь растение: фикус",
        "Расписание полива",
    ],
}


def agent_quick_prompts(agent_id: str) -> InlineKeyboardMarkup | None:
    """Кнопки с примерами запросов для агента."""
    prompts = AGENT_QUICK_PROMPTS.get(agent_id, [])
    if not prompts:
        return None

    rows = []
    for prompt in prompts:
        # callback_data ограничен 64 байтами — используем хеш
        # Вместо этого сделаем короткий ID: "qp:{agent_id}:{index}"
        idx = prompts.index(prompt)
        rows.append([
            InlineKeyboardButton(
                text=f"💡 {prompt[:50]}",
                callback_data=f"qp:{agent_id}:{idx}",
            )
        ])

    rows.append([
        InlineKeyboardButton(
            text="✍️ Свой вопрос",
            callback_data=f"agent_ask:{agent_id}",
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)
