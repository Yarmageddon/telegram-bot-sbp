"""
agent_handlers.py — Router с хендлерами для агентов.

Новое:
- Кнопки меню агентов (abtn:*)
- Кнопка «🔙 Назад» (agents:menu)
- Поддержка upload_file для Аналитика
- Команды /exit и /reset
"""

import logging

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from agents import get_agent, get_available_agents
from agent_keyboards import (
    agents_main_menu,
    agent_menu,
    back_to_agent_menu,
)
from agent_router import route_to_agent, is_llm_configured

logger = logging.getLogger(__name__)

agents_router = Router(name="agents")


# ═══════════════════════════════════════════════════════════════
# FSM
# ═══════════════════════════════════════════════════════════════

class AgentStates(StatesGroup):
    browsing = State()          # смотрит список агентов
    chatting = State()          # в чате с агентом
    waiting_input = State()     # ждём текстовый ввод
    waiting_file = State()      # ждём загрузку файла


# ═══════════════════════════════════════════════════════════════
# /agents — СПИСОК АГЕНТОВ
# ═══════════════════════════════════════════════════════════════

@agents_router.message(Command("agents"))
async def cmd_agents(message: Message, state: FSMContext):
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
# ВЫБОР АГЕНТА
# ═══════════════════════════════════════════════════════════════

@agents_router.callback_query(F.data.startswith("agent:"))
async def callback_select_agent(callback: CallbackQuery, state: FSMContext):
    agent_id = callback.data.split(":", 1)[1]
    agent = get_agent(agent_id)

    if not agent:
        await callback.answer("Агент не найден", show_alert=True)
        return

    # Сбрасываем состояние на «в чате с этим агентом», но историю не трогаем
    await state.set_state(AgentStates.chatting)
    data = await state.get_data()
    if data.get("agent_id") != agent_id:
        await state.update_data(agent_id=agent_id, agent_history=[])

    header = (
        f"{agent.emoji} *{agent.name}*\n\n"
        f"_{agent.description}_\n\n"
        f"Выбери действие ниже или напиши свой вопрос:"
    )

    await callback.message.edit_text(
        header,
        reply_markup=agent_menu(agent_id),
        parse_mode="Markdown",
    )
    await callback.answer()


# ═══════════════════════════════════════════════════════════════
# НАЖАТИЕ НА КНОПКУ АГЕНТА (abtn:<agent_id>:<idx>)
# ═══════════════════════════════════════════════════════════════

@agents_router.callback_query(F.data.startswith("abtn:"))
async def callback_agent_button(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия на кнопку из меню агента."""
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer("Ошибка кнопки", show_alert=True)
        return

    _, agent_id, idx_str = parts
    try:
        idx = int(idx_str)
    except ValueError:
        await callback.answer("Ошибка индекса", show_alert=True)
        return

    agent = get_agent(agent_id)
    if not agent:
        await callback.answer("Агент не найден", show_alert=True)
        return

    if idx >= len(agent.menu_buttons):
        await callback.answer("Кнопка не найдена", show_alert=True)
        return

    button = agent.menu_buttons[idx]

    # Спец-действие: загрузка файла
    if button.action == "upload_file":
        await state.set_state(AgentStates.waiting_file)
        await state.update_data(agent_id=agent_id)
        await callback.message.edit_text(
            f"{agent.emoji} *{agent.name}*\n\n"
            f"📎 Загрузи файл (PDF, DOCX, CSV, XLSX).\n"
            f"Я его проанализирую и верну отчёт.",
            parse_mode="Markdown",
        )
        await callback.answer()
        return

    # Обычная кнопка — отправляем prompt в LLM
    await state.set_state(AgentStates.chatting)
    await state.update_data(agent_id=agent_id)

    # Небольшая индикация
    await callback.message.edit_text(
        f"{agent.emoji} *{agent.name}*\n\n"
        f"❓ _{button.label}_\n\n"
        f"⏳ Обрабатываю…",
        parse_mode="Markdown",
    )

    await _process_agent_request(
        message=callback.message,
        state=state,
        agent_id=agent_id,
        user_text=button.prompt,
        user_id=callback.from_user.id,
        is_callback=True,
    )
    await callback.answer()


# ═══════════════════════════════════════════════════════════════
# СВОБОДНЫЙ ТЕКСТ В ЧАТЕ С АГЕНТОМ
# ═══════════════════════════════════════════════════════════════

@agents_router.message(AgentStates.chatting, F.text)
async def handle_chatting(message: Message, state: FSMContext):
    data = await state.get_data()
    agent_id = data.get("agent_id")

    if not agent_id:
        await message.answer("Агент не выбран. Начни заново: /agents")
        return

    await _process_agent_request(
        message=message,
        state=state,
        agent_id=agent_id,
        user_text=message.text,
        user_id=message.from_user.id,
    )


# ═══════════════════════════════════════════════════════════════
# ОЖИДАНИЕ ФАЙЛА (Аналитик)
# ═══════════════════════════════════════════════════════════════

@agents_router.message(AgentStates.waiting_file, F.document)
async def handle_document(message: Message, state: FSMContext):
    """Пользователь загрузил файл."""
    data = await state.get_data()
    agent_id = data.get("agent_id")

    if not agent_id:
        await message.answer("Агент не выбран. /agents")
        return

    doc = message.document
    file_name = doc.file_name or "файл"
    file_size = doc.file_size or 0

    # Лимит Telegram Bot API — 20 MB на скачивание
    if file_size > 20 * 1024 * 1024:
        await message.answer("⚠️ Файл больше 20 MB. Telegram не отдаст его боту.")
        return

    # Пока — только подтверждение. Реальный парсинг в Этапе 4.
    await message.answer(
        f"📎 Файл получен: *{file_name}*\n"
        f"Размер: {file_size / 1024:.1f} KB\n\n"
        f"⚙️ Обработка файлов будет добавлена на следующем этапе.\n"
        f"Пока могу принять только текстовое описание задачи.",
        parse_mode="Markdown",
    )

    # Возвращаем состояние в чат
    await state.set_state(AgentStates.chatting)


@agents_router.message(AgentStates.waiting_file, F.text)
async def handle_file_fallback(message: Message, state: FSMContext):
    """Пользователь написал текст вместо файла — обрабатываем как обычно."""
    data = await state.get_data()
    agent_id = data.get("agent_id")
    if not agent_id:
        await message.answer("Агент не выбран. /agents")
        return

    await state.set_state(AgentStates.chatting)
    await _process_agent_request(
        message=message,
        state=state,
        agent_id=agent_id,
        user_text=message.text,
        user_id=message.from_user.id,
    )


# ═══════════════════════════════════════════════════════════════
# ВЫХОД / СБРОС
# ═══════════════════════════════════════════════════════════════

@agents_router.message(Command("exit"), StateFilter(AgentStates.chatting))
@agents_router.message(Command("exit"), StateFilter(AgentStates.waiting_input))
@agents_router.message(Command("exit"), StateFilter(AgentStates.waiting_file))
async def cmd_exit(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Вышел из чата с агентом. Команды:\n"
        "/agents — меню агентов\n"
        "/start — главное меню",
    )


@agents_router.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("♻️ Состояние сброшено. /agents — начать заново.")


# ═══════════════════════════════════════════════════════════════
# ЕДИНАЯ ОБРАБОТКА ЗАПРОСА
# ═══════════════════════════════════════════════════════════════

async def _process_agent_request(
    message: Message,
    state: FSMContext,
    agent_id: str,
    user_text: str,
    user_id: int,
    is_callback: bool = False,
) -> None:
    """Отправка запроса в LLM-роутер и вывод ответа."""
    agent = get_agent(agent_id)
    if not agent:
        await message.answer("⚠️ Агент потерялся. /agents")
        return

    try:
        await message.bot.send_chat_action(message.chat.id, "typing")
    except Exception:
        pass

    data = await state.get_data()
    history = data.get("agent_history", [])

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

    # Обновляем историю
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": response})
    if len(history) > 20:
        history = history[-20:]
    await state.update_data(agent_history=history)

    # Отправляем ответ. Если пришли из callback — редактируем сообщение,
    # иначе отправляем новое.
    keyboard = back_to_agent_menu(agent_id)
    max_len = 4000

    if is_callback:
        # Пытаемся отредактировать, чтобы не плодить сообщения
        try:
            if len(response) <= max_len:
                await message.edit_text(
                    response,
                    reply_markup=keyboard,
                    parse_mode="Markdown",
                )
            else:
                # Длинный ответ — редактируем первую часть, остальное новыми
                await message.edit_text(
                    response[:max_len],
                    parse_mode="Markdown",
                )
                for i in range(max_len, len(response), max_len):
                    chunk = response[i:i + max_len]
                    is_last = i + max_len >= len(response)
                    await message.answer(
                        chunk,
                        reply_markup=keyboard if is_last else None,
                        parse_mode="Markdown",
                    )
            return
        except Exception as e:
            logger.warning(f"edit_text не сработал, шлю новым: {e}")

    # Обычная отправка (из текстового сообщения)
    if len(response) <= max_len:
        await message.answer(
            response,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
    else:
        for i in range(0, len(response), max_len):
            chunk = response[i:i + max_len]
            is_last = i + max_len >= len(response)
            await message.answer(
                chunk,
                reply_markup=keyboard if is_last else None,
                parse_mode="Markdown",
            )


# ═══════════════════════════════════════════════════════════════
# НЕ-ТЕКСТ В ЧАТЕ С АГЕНТОМ
# ═══════════════════════════════════════════════════════════════

@agents_router.message(AgentStates.chatting)
@agents_router.message(AgentStates.waiting_input)
async def handle_non_text(message: Message, state: FSMContext):
    await message.answer(
        "🤔 Я работаю только с текстом и файлами (в Аналитике). "
        "Напиши свой вопрос словами."
    )
