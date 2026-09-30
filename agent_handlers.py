"""
agent_handlers.py — Router с хендлерами для агентов.

Подключается в bot.py одной строкой:
    from agent_handlers import agents_router
    dp.include_router(agents_router)
"""

import logging

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from agents import (
    get_agent,
    get_agents_by_category,
    get_category_title,
    get_available_agents,
)
from agent_keyboards import (
    agents_main_menu,
    category_menu,
    all_agents_menu,
    agent_action_menu,
    agent_chat_keyboard,
    agent_quick_prompts,
    AGENT_QUICK_PROMPTS,
)
from agent_router import route_to_agent, is_llm_configured

logger = logging.getLogger(__name__)

# Создаём изолированный роутер для агентов
agents_router = Router(name="agents")


# ═══════════════════════════════════════════════════════════════
# FSM-СОСТОЯНИЯ
# ═══════════════════════════════════════════════════════════════

class AgentStates(StatesGroup):
    """Состояния для работы с агентами."""
    browsing = State()        # Смотрит меню агентов
    chatting = State()        # В диалоге с агентом
    waiting_input = State()   # Ждём ввод после «Задать вопрос»


# ═══════════════════════════════════════════════════════════════
# ХЕНДЛЕР 1: /agents — главное меню
# ═══════════════════════════════════════════════════════════════

@agents_router.message(Command("agents"))
async def cmd_agents(message: Message, state: FSMContext):
    """Показать список всех агентов."""
    await state.clear()
    await state.set_state(AgentStates.browsing)

    total = len(get_available_agents())
    llm_note = "" if is_llm_configured() else "\n\n⚠️ _AI не настроен — демо-режим_"

    await message.answer(
        f"🤖 *Агенты на связи!*\n\n"
        f"Доступно агентов: *{total}*\n"
        f"Выбери нужного:{llm_note}",
        reply_markup=agents_main_menu(),
        parse_mode="Markdown",
    )


# ═══════════════════════════════════════════════════════════════
# ХЕНДЛЕР 2: callback "agents:menu" — вернуться к категориям
# ═══════════════════════════════════════════════════════════════

@agents_router.callback_query(F.data == "agents:menu")
async def callback_agents_menu(callback: CallbackQuery, state: FSMContext):
    """Вернуться к списку агентов."""
    await state.set_state(AgentStates.browsing)
    total = len(get_available_agents())
    await callback.message.edit_text(
        f"🤖 *Агенты на связи!*\n\n"
        f"Доступно агентов: *{total}*\n"
        f"Выбери нужного:",
        reply_markup=agents_main_menu(),
        parse_mode="Markdown",
    )
    await callback.answer()


# ═══════════════════════════════════════════════════════════════
# ХЕНДЛЕР 3: callback "agent_cat:<category>" — меню категории
# ═══════════════════════════════════════════════════════════════

@agents_router.callback_query(F.data.startswith("agent_cat:"))
async def callback_category(callback: CallbackQuery, state: FSMContext):
    """Показать агентов внутри категории."""
    category = callback.data.split(":", 1)[1]
    agents_in_cat = get_agents_by_category(category)

    if not agents_in_cat:
        await callback.answer("В этой категории пока нет агентов", show_alert=True)
        return

    await state.set_state(AgentStates.browsing)
    title = get_category_title(category)

    await callback.message.edit_text(
        f"{title}\n\n"
        f"Агентов в категории: *{len(agents_in_cat)}*\n"
        f"Выбери одного:",
        reply_markup=category_menu(category),
        parse_mode="Markdown",
    )
    await callback.answer()


# ═══════════════════════════════════════════════════════════════
# ХЕНДЛЕР 4: callback "agent_all" — плоский список
# ═══════════════════════════════════════════════════════════════

@agents_router.callback_query(F.data == "agent_all")
async def callback_all_agents(callback: CallbackQuery, state: FSMContext):
    """Показать всех агентов плоским списком."""
    await state.set_state(AgentStates.browsing)
    total = len(get_available_agents())
    await callback.message.edit_text(
        f"🤖 *Все агенты* ({total})\n\nВыбери нужного:",
        reply_markup=all_agents_menu(),
        parse_mode="Markdown",
    )
    await callback.answer()


# ═══════════════════════════════════════════════════════════════
# ХЕНДЛЕР 5: callback "agent:<id>" — открыть агента
# ═══════════════════════════════════════════════════════════════

@agents_router.callback_query(F.data.startswith("agent:"))
async def callback_select_agent(callback: CallbackQuery, state: FSMContext):
    """Пользователь выбрал агента."""
    agent_id = callback.data.split(":", 1)[1]
    agent = get_agent(agent_id)

    if not agent:
        await callback.answer("Агент не найден", show_alert=True)
        return

    # Сбрасываем историю диалога — начинаем с чистого листа
    await state.set_state(AgentStates.chatting)
    await state.update_data(agent_id=agent_id, agent_history=[])

    header = (
        f"{agent.emoji} *{agent.name}*\n\n"
        f"_{agent.description}_\n\n"
        f"🛠 *Инструментов:* {len(agent.tools)}\n\n"
        f"Выбери готовый вопрос ниже или напиши свой:"
    )

    # Если есть быстрые подсказки — показываем их
    quick_kb = agent_quick_prompts(agent_id)

    if quick_kb:
        await callback.message.edit_text(
            header,
            reply_markup=quick_kb,
            parse_mode="Markdown",
        )
    else:
        # Если подсказок нет — просто открываем чат
        await callback.message.edit_text(
            header,
            reply_markup=agent_action_menu(agent_id),
            parse_mode="Markdown",
        )
    await callback.answer()


# ═══════════════════════════════════════════════════════════════
# ХЕНДЛЕР 6: callback "qp:<agent>:<idx>" — быстрый вопрос
# ═══════════════════════════════════════════════════════════════

@agents_router.callback_query(F.data.startswith("qp:"))
async def callback_quick_prompt(callback: CallbackQuery, state: FSMContext):
    """Пользователь нажал на готовый вопрос."""
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer("Ошибка", show_alert=True)
        return

    _, agent_id, idx_str = parts
    try:
        idx = int(idx_str)
    except ValueError:
        await callback.answer("Ошибка", show_alert=True)
        return

    agent = get_agent(agent_id)
    if not agent:
        await callback.answer("Агент не найден", show_alert=True)
        return

    prompts = AGENT_QUICK_PROMPTS.get(agent_id, [])
    if idx >= len(prompts):
        await callback.answer("Вопрос не найден", show_alert=True)
        return

    prompt_text = prompts[idx]

    # Показываем пользователю, что он "выбрал"
    await callback.message.edit_text(
        f"{agent.emoji} *{agent.name}*\n\n"
        f"❓ _{prompt_text}_\n\n"
        f"⏳ Думаю...",
        parse_mode="Markdown",
    )

    # Отправляем в роутер
    await _process_agent_request(
        callback.message, state, agent_id, prompt_text,
        user_id=callback.from_user.id,
    )
    await callback.answer()


# ═══════════════════════════════════════════════════════════════
# ХЕНДЛЕР 7: callback "agent_ask:<id>" — попросить ввод
# ═══════════════════════════════════════════════════════════════

@agents_router.callback_query(F.data.startswith("agent_ask:"))
async def callback_agent_ask(callback: CallbackQuery, state: FSMContext):
    """Пользователь нажал «Задать вопрос»."""
    agent_id = callback.data.split(":", 1)[1]
    agent = get_agent(agent_id)

    if not agent:
        await callback.answer("Агент не найден", show_alert=True)
        return

    await state.set_state(AgentStates.waiting_input)
    await state.update_data(agent_id=agent_id)

    await callback.message.edit_text(
        f"{agent.emoji} *{agent.name}*\n\n"
        f"✍️ Напиши свой вопрос:",
        parse_mode="Markdown",
    )
    await callback.answer()


# ═══════════════════════════════════════════════════════════════
# ХЕНДЛЕР 8: callback "agent_clear:<id>" — очистить историю
# ═══════════════════════════════════════════════════════════════

@agents_router.callback_query(F.data.startswith("agent_clear:"))
async def callback_clear_history(callback: CallbackQuery, state: FSMContext):
    """Очистить историю диалога с агентом."""
    agent_id = callback.data.split(":", 1)[1]
    agent = get_agent(agent_id)

    if not agent:
        await callback.answer("Агент не найден", show_alert=True)
        return

    await state.update_data(agent_history=[])
    await state.set_state(AgentStates.chatting)

    await callback.message.edit_text(
        f"{agent.emoji} *{agent.name}*\n\n"
        f"🗑 История очищена. О чём поговорим?",
        reply_markup=agent_action_menu(agent_id),
        parse_mode="Markdown",
    )
    await callback.answer("История очищена")


# ═══════════════════════════════════════════════════════════════
# ХЕНДЛЕР 9: сообщение в состоянии waiting_input
# ═══════════════════════════════════════════════════════════════

@agents_router.message(AgentStates.waiting_input, F.text)
async def handle_waiting_input(message: Message, state: FSMContext):
    """Пользователь ввёл свой вопрос после нажатия «Задать вопрос»."""
    data = await state.get_data()
    agent_id = data.get("agent_id")

    if not agent_id:
        await message.answer("Агент не выбран. Начни заново: /agents")
        return

    # Переключаемся в режим чата
    await state.set_state(AgentStates.chatting)
    await state.update_data(agent_history=[])

    await _process_agent_request(
        message, state, agent_id, message.text,
        user_id=message.from_user.id,
    )


# ═══════════════════════════════════════════════════════════════
# ХЕНДЛЕР 10: сообщение в состоянии chatting
# ═══════════════════════════════════════════════════════════════

@agents_router.message(AgentStates.chatting, F.text)
async def handle_chatting(message: Message, state: FSMContext):
    """Пользователь пишет агенту в режиме чата."""
    data = await state.get_data()
    agent_id = data.get("agent_id")

    if not agent_id:
        await message.answer("Агент не выбран. Начни заново: /agents")
        return

    await _process_agent_request(
        message, state, agent_id, message.text,
        user_id=message.from_user.id,
    )


# ═══════════════════════════════════════════════════════════════
# ОБЩАЯ ФУНКЦИЯ ОБРАБОТКИ ЗАПРОСА
# ═══════════════════════════════════════════════════════════════

async def _process_agent_request(
    message: Message,
    state: FSMContext,
    agent_id: str,
    user_text: str,
    user_id: int,
) -> None:
    """Отправить запрос в роутер и показать ответ."""
    agent = get_agent(agent_id)
    if not agent:
        await message.answer("⚠️ Агент потерялся. Начни заново: /agents")
        return

    # Индикатор "печатает..."
    try:
        await message.bot.send_chat_action(message.chat.id, "typing")
    except Exception:
        pass

    # Получаем историю
    data = await state.get_data()
    history = data.get("agent_history", [])

    # Вызываем роутер
    try:
        response = await route_to_agent(
            user_message=user_text,
            agent_id=agent_id,
            user_id=user_id,
            context=history,
        )
    except Exception as e:
        logger.exception(f"[HANDLERS] Ошибка роутера: {e}")
        response = f"⚠️ Что-то пошло не так: {type(e).__name__}"

    # Обновляем историю (храним последние 20 сообщений)
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": response})
    if len(history) > 20:
        history = history[-20:]
    await state.update_data(agent_history=history)

    # Отправляем ответ
    # Telegram ограничивает длину сообщения 4096 символами
    max_len = 4000
    if len(response) <= max_len:
        await message.answer(
            response,
            reply_markup=agent_chat_keyboard(agent_id),
            parse_mode="Markdown",
        )
    else:
        # Разбиваем длинный ответ на части
        for i in range(0, len(response), max_len):
            chunk = response[i:i + max_len]
            is_last = i + max_len >= len(response)
            await message.answer(
                chunk,
                reply_markup=agent_chat_keyboard(agent_id) if is_last else None,
                parse_mode="Markdown",
            )


# ═══════════════════════════════════════════════════════════════
# ХЕНДЛЕР 11: /exit — выйти из чата агента
# ═══════════════════════════════════════════════════════════════

@agents_router.message(Command("exit"), StateFilter(AgentStates.chatting))
@agents_router.message(Command("exit"), StateFilter(AgentStates.waiting_input))
async def cmd_exit(message: Message, state: FSMContext):
    """Выйти из чата с агентом."""
    await state.clear()
    await message.answer(
        "👋 Вышел из чата с агентом. Команды:\n"
        "/agents — меню агентов\n"
        "/start — главное меню",
    )


# ═══════════════════════════════════════════════════════════════
# ХЕНДЛЕР 12: /reset — сбросить состояние
# ═══════════════════════════════════════════════════════════════

@agents_router.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext):
    """Полный сброс состояния."""
    await state.clear()
    await message.answer("♻️ Состояние сброшено. /agents — начать заново.")


# ═══════════════════════════════════════════════════════════════
# ХЕНДЛЕР 13: подсказка, если в чате агента пришёл не текст
# ═══════════════════════════════════════════════════════════════

@agents_router.message(AgentStates.chatting)
@agents_router.message(AgentStates.waiting_input)
async def handle_non_text(message: Message, state: FSMContext):
    """Если пользователь прислал не текст в режиме чата с агентом."""
    await message.answer(
        "🤔 Я умею работать только с текстом. Напиши свой вопрос словами."
    )
