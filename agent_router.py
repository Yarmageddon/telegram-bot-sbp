"""
agent_router.py — Роутер запросов между агентами.

Основная задача:
1. Принять сообщение пользователя + agent_id.
2. Достать конфиг агента из agents.py.
3. Подтянуть схемы инструментов из tools.py (только те, что нужны агенту).
4. Вызвать LLM с этими инструментами (OpenAI function calling).
5. Если LLM запросил инструменты — выполнить их через execute_tool() и
   отправить результаты обратно в LLM (agentic loop).
6. Вернуть финальный текст пользователю.

Поддерживает OpenAI и OpenRouter. Работает с любой моделью, которая
умеет function calling (gpt-4o, gpt-4.1, claude-3.5, llama-3.1 и т.д.).
"""

import os
import json
import logging
import asyncio
from typing import Optional

import httpx

from agents import AgentConfig, get_agent, get_available_agents
from tools import execute_tool, get_tools_for_agent

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

# По умолчанию — OpenAI. Если задан OPENROUTER_API_KEY, используем OpenRouter.
DEFAULT_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

LLM_API_URL = os.getenv(
    "LLM_API_URL",
    DEFAULT_OPENROUTER_URL if OPENROUTER_API_KEY else DEFAULT_OPENAI_URL,
)
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# Максимальное количество итераций agentic loop (LLM ↔ tools).
# 5 — с запасом хватает для сложных сценариев, но защищает от бесконечного цикла.
MAX_TOOL_ITERATIONS = int(os.getenv("MAX_TOOL_ITERATIONS", "5"))

# Таймауты
REQUEST_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))


# ═══════════════════════════════════════════════════════════════
# ПРОВЕРКА НАСТРОЕК
# ═══════════════════════════════════════════════════════════════

def is_llm_configured() -> bool:
    """Настроен ли доступ к LLM."""
    return bool(OPENAI_API_KEY or OPENROUTER_API_KEY)


def get_llm_info() -> dict:
    """Информация о текущей LLM (для логов и отладки)."""
    provider = "openrouter" if OPENROUTER_API_KEY else ("openai" if OPENAI_API_KEY else "none")
    return {
        "provider": provider,
        "model": LLM_MODEL,
        "url": LLM_API_URL,
        "configured": is_llm_configured(),
    }


def _get_llm_headers() -> dict:
    """Заголовки для LLM API."""
    headers = {
        "Content-Type": "application/json",
    }
    if OPENROUTER_API_KEY:
        headers["Authorization"] = f"Bearer {OPENROUTER_API_KEY}"
        # OpenRouter рекомендует передавать Referer и X-Title
        headers["HTTP-Referer"] = "https://github.com/Yarmageddon/telegram-bot-sbp"
        headers["X-Title"] = "Telegram SBP Agents"
    elif OPENAI_API_KEY:
        headers["Authorization"] = f"Bearer {OPENAI_API_KEY}"
    return headers


# ═══════════════════════════════════════════════════════════════
# ВЫЗОВ LLM
# ═══════════════════════════════════════════════════════════════

async def _call_llm(
    messages: list[dict],
    temperature: float = 0.7,
    tools: Optional[list[dict]] = None,
    model: Optional[str] = None,
) -> dict:
    """
    Низкоуровневый вызов LLM API.

    Возвращает полный ответ API. Бросает httpx.HTTPStatusError при ошибке.
    """
    payload: dict = {
        "model": model or LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        resp = await client.post(
            LLM_API_URL,
            headers=_get_llm_headers(),
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


# ═══════════════════════════════════════════════════════════════
# AGENTIC LOOP (LLM ↔ TOOLS)
# ═══════════════════════════════════════════════════════════════

async def _run_agentic_loop(
    messages: list[dict],
    agent: AgentConfig,
    user_id: int,
) -> str:
    """
    Запускает цикл: LLM → tool_calls → execute tools → LLM → ...

    Возвращает финальный текст ответа.
    """
    # Схемы инструментов именно для этого агента
    tools_schemas = get_tools_for_agent(agent.tools) if agent.tools else None

    if tools_schemas:
        logger.info(
            f"[ROUTER] Агент {agent.id}: доступно {len(tools_schemas)} инструментов"
        )

    for iteration in range(MAX_TOOL_ITERATIONS):
        logger.debug(f"[ROUTER] Итерация {iteration + 1}/{MAX_TOOL_ITERATIONS}")

        response = await _call_llm(
            messages=messages,
            temperature=agent.temperature,
            tools=tools_schemas,
        )

        if not response.get("choices"):
            logger.error(f"[ROUTER] Пустой ответ от LLM: {response}")
            return "⚠️ Модель вернула пустой ответ. Попробуй ещё раз."

        choice = response["choices"][0]["message"]
        tool_calls = choice.get("tool_calls") or []

        # Если инструментов нет — возвращаем текст
        if not tool_calls:
            content = choice.get("content") or ""
            if not content.strip():
                return "⚠️ Модель не дала ответа. Попробуй переформулировать."
            return content

        # Добавляем ответ LLM в историю (с tool_calls)
        messages.append({
            "role": "assistant",
            "content": choice.get("content"),
            "tool_calls": tool_calls,
        })

        # Выполняем каждый вызов инструмента
        for tc in tool_calls:
            tool_name = tc["function"]["name"]
            tool_args_raw = tc["function"].get("arguments", "{}")

            # Парсим аргументы (могут прийти как строка)
            try:
                tool_args = json.loads(tool_args_raw) if isinstance(tool_args_raw, str) else tool_args_raw
            except json.JSONDecodeError as e:
                logger.error(f"[ROUTER] Ошибка парсинга аргументов {tool_name}: {e}")
                tool_args = {}

            logger.info(f"[ROUTER] 🔧 {tool_name}({tool_args})")

            # Выполняем инструмент (execute_tool сам подставит user_id)
            result = await execute_tool(tool_name, user_id=user_id, **tool_args)

            # Отправляем результат обратно в LLM
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

    # Если вышли из цикла — значит, превысили лимит итераций
    logger.warning(
        f"[ROUTER] Превышен лимит итераций ({MAX_TOOL_ITERATIONS}) для агента {agent.id}"
    )
    # Делаем финальный вызов без инструментов, чтобы получить текст
    try:
        final_response = await _call_llm(
            messages=messages,
            temperature=agent.temperature,
            tools=None,
        )
        return final_response["choices"][0]["message"].get("content") or \
               "⚠️ Слишком много шагов. Попробуй упростить запрос."
    except Exception as e:
        logger.error(f"[ROUTER] Финальный вызов упал: {e}")
        return "⚠️ Не удалось завершить задачу. Попробуй ещё раз."


# ═══════════════════════════════════════════════════════════════
# ПУБЛИЧНЫЙ API: ROUTE TO AGENT
# ═══════════════════════════════════════════════════════════════

async def route_to_agent(
    user_message: str,
    agent_id: str,
    user_id: int,
    context: Optional[list[dict]] = None,
) -> str:
    """
    Основная функция. Принимает сообщение пользователя, возвращает ответ агента.

    Args:
        user_message: текст запроса от пользователя
        agent_id: ID агента из agents.py
        user_id: Telegram user_id (используется инструментами)
        context: предыдущие сообщения [{role, content}, ...]

    Returns:
        Текст ответа для отправки пользователю.
    """
    # 1. Достаём агента
    agent = get_agent(agent_id)
    if not agent:
        logger.error(f"[ROUTER] Агент '{agent_id}' не найден")
        return "⚠️ Агент не найден. Выбери другого: /agents"

    if not agent.is_available:
        return f"⚠️ Агент «{agent.name}» временно недоступен."

    logger.info(
        f"[ROUTER] → {agent.id} | user={user_id} | msg={user_message[:80]!r}"
    )

    # 2. Если LLM не настроен — отдаём fallback
    if not is_llm_configured():
        return _fallback_response(agent, user_message)

    # 3. Собираем сообщения
    messages: list[dict] = [
        {"role": "system", "content": agent.system_prompt},
    ]

    # Добавляем контекст (история диалога)
    if context:
        # Ограничиваем историю последними 20 сообщениями
        for msg in context[-20:]:
            if msg.get("role") in ("user", "assistant") and msg.get("content"):
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

    messages.append({"role": "user", "content": user_message})

    # 4. Запускаем agentic loop
    try:
        answer = await _run_agentic_loop(messages, agent, user_id)
        logger.info(f"[ROUTER] ← {agent.id} | {len(answer)} символов")
        return answer

    except httpx.HTTPStatusError as e:
        logger.error(
            f"[ROUTER] HTTP ошибка LLM: {e.response.status_code} — {e.response.text[:200]}"
        )
        if e.response.status_code == 401:
            return "⚠️ Ошибка авторизации LLM. Проверь API-ключ."
        if e.response.status_code == 429:
            return "⚠️ Слишком много запросов. Подожди немного и попробуй снова."
        return f"⚠️ Ошибка LLM ({e.response.status_code}). Попробуй позже."

    except httpx.TimeoutException:
        logger.error(f"[ROUTER] Таймаут LLM для агента {agent.id}")
        return "⏱️ Модель не ответила вовремя. Попробуй ещё раз."

    except Exception as e:
        logger.exception(f"[ROUTER] Неожиданная ошибка: {e}")
        return f"⚠️ Что-то пошло не так: {type(e).__name__}. Попробуй позже."


# ═══════════════════════════════════════════════════════════════
# FALLBACK (демо-режим без API)
# ═══════════════════════════════════════════════════════════════

def _fallback_response(agent: AgentConfig, user_message: str) -> str:
    """
    Заглушка, если нет API-ключа.
    Показывает, что агент «живой», и объясняет, как включить AI.
    """
    tools_list = ""
    if agent.tools:
        tools_list = "\n\n🛠 *Доступные инструменты:*\n" + "\n".join(
            f"  • `{t}`" for t in agent.tools
        )

    return (
        f"{agent.emoji} *{agent.name}* на связи!\n\n"
        f"_{agent.description}_\n\n"
        f"📝 Ты сказал: «{user_message}»\n"
        f"{tools_list}\n\n"
        f"⚙️ _API-ключ LLM не настроен — я работаю в демо-режиме._\n"
        f"_Добавь `OPENAI_API_KEY` или `OPENROUTER_API_KEY` в `.env`, "
        f"чтобы я начал отвечать по-настоящему._"
    )


# ═══════════════════════════════════════════════════════════════
# УТИЛИТЫ ДЛЯ ОТЛАДКИ
# ═══════════════════════════════════════════════════════════════

async def preview_agent(agent_id: str) -> dict:
    """
    Показать, что «видит» агент: промпт, инструменты, схемы.
    Полезно для отладки и проверки конфигурации.
    """
    agent = get_agent(agent_id)
    if not agent:
        return {"status": "error", "message": f"Агент '{agent_id}' не найден"}

    schemas = get_tools_for_agent(agent.tools)
    return {
        "status": "ok",
        "agent": {
            "id": agent.id,
            "name": agent.name,
            "emoji": agent.emoji,
            "category": agent.category,
            "temperature": agent.temperature,
            "description": agent.description,
        },
        "system_prompt_length": len(agent.system_prompt),
        "system_prompt_preview": agent.system_prompt[:300] + "...",
        "tools_declared": agent.tools,
        "tools_available": [s["function"]["name"] for s in schemas],
        "tools_missing": [t for t in agent.tools if t not in
                          [s["function"]["name"] for s in schemas]],
    }


async def healthcheck() -> dict:
    """
    Проверить работоспособность LLM. Делает минимальный запрос.
    Полезно при старте бота.
    """
    info = get_llm_info()
    if not info["configured"]:
        return {"status": "disabled", "reason": "no_api_key", **info}

    try:
        response = await _call_llm(
            messages=[{"role": "user", "content": "ping"}],
            temperature=0.0,
        )
        content = response["choices"][0]["message"].get("content", "")
        return {
            "status": "ok",
            "response_preview": content[:50],
            **info,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), **info}


# ═══════════════════════════════════════════════════════════════
# САМОПРОВЕРКА
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import asyncio

    async def _test():
        print("═══ Agent Router — самопроверка ═══\n")

        # 1. Проверка конфигурации LLM
        info = get_llm_info()
        print(f"LLM provider: {info['provider']}")
        print(f"LLM model:    {info['model']}")
        print(f"Configured:   {'✅' if info['configured'] else '❌ (демо-режим)'}\n")

        # 2. Проверка всех агентов
        from agents import AGENTS
        print(f"── Проверка {len(AGENTS)} агентов ──\n")

        broken = []
        for agent_id in AGENTS:
            preview = await preview_agent(agent_id)
            a = preview["agent"]
            missing = preview["tools_missing"]

            status = "✅" if not missing else "⚠️"
            print(
                f"{status} {a['emoji']} {a['name']:22s} "
                f"tools={len(preview['tools_available']):2d}/{len(preview['tools_declared']):2d} "
                f"prompt={preview['system_prompt_length']} симв."
            )
            if missing:
                print(f"    ❌ отсутствуют схемы: {missing}")
                broken.append((agent_id, missing))

        if broken:
            print(f"\n⚠️ Проблемы у {len(broken)} агентов")
        else:
            print(f"\n✅ Все агенты настроены корректно")

        # 3. Демо-запрос (только если LLM настроен)
        if info["configured"]:
            print("\n── Демо-запрос к погодному агенту ──")
            answer = await route_to_agent(
                user_message="Какая погода в Москве?",
                agent_id="weather",
                user_id=12345,
            )
            print(f"Ответ: {answer[:300]}")
        else:
            print("\n── Демо в fallback-режиме ──")
            answer = await route_to_agent(
                user_message="Какая погода в Москве?",
                agent_id="weather",
                user_id=12345,
            )
            print(answer[:300])

    asyncio.run(_test())
