"""
agent_router.py — Роутер запросов между всеми 16 агентами.

Работает с любым агентом из agents.py автоматически:
- берёт system_prompt агента,
- подтягивает нужные схемы из tools.py,
- гоняет agentic loop (LLM ↔ tool calls ↔ LLM),
- возвращает финальный текст.

Исправления:
- убран tool_choice: "auto" (вызывает 400 у некоторых моделей),
- добавлена нормализация аргументов tool_calls,
- добавлено развёрнутое логирование ошибок LLM,
- добавлен retry без tools при ошибке 400.
"""

import os
import json
import logging
from typing import Optional

import httpx

from agents import AgentConfig, get_agent
from tools import execute_tool, get_tools_for_agent

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

# Определяем провайдера по приоритету
if GROQ_API_KEY:
    _DEFAULT_URL = "https://api.groq.com/openai/v1/chat/completions"
elif OPENROUTER_API_KEY:
    _DEFAULT_URL = "https://openrouter.ai/api/v1/chat/completions"
else:
    _DEFAULT_URL = "https://api.openai.com/v1/chat/completions"

LLM_API_URL = os.getenv("LLM_API_URL", _DEFAULT_URL)
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
REQUEST_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))
MAX_TOOL_ITERATIONS = int(os.getenv("MAX_TOOL_ITERATIONS", "5"))
SEND_TOOL_CHOICE = os.getenv("SEND_TOOL_CHOICE", "false").lower() in ("1", "true", "yes")

# Флаг: отправлять ли tool_choice: "auto".
# Некоторые модели (Gemini, Qwen, DeepSeek) падают с 400, если он указан.
# По умолчанию — НЕ отправляем.
SEND_TOOL_CHOICE = os.getenv("SEND_TOOL_CHOICE", "false").lower() in ("1", "true", "yes")


# ═══════════════════════════════════════════════════════════════
# УТИЛИТЫ КОНФИГУРАЦИИ
# ═══════════════════════════════════════════════════════════════

def is_llm_configured() -> bool:
    return bool(GROQ_API_KEY or OPENROUTER_API_KEY or OPENAI_API_KEY)

def get_llm_info() -> dict:
    if GROQ_API_KEY:
        provider = "groq"
    elif OPENROUTER_API_KEY:
        provider = "openrouter"
    elif OPENAI_API_KEY:
        provider = "openai"
    else:
        provider = "none"
    return {
        "provider": provider,
        "model": LLM_MODEL,
        "url": LLM_API_URL,
        "configured": is_llm_configured(),
    }


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if GROQ_API_KEY:
        h["Authorization"] = f"Bearer {GROQ_API_KEY}"
    elif OPENROUTER_API_KEY:
        h["Authorization"] = f"Bearer {OPENROUTER_API_KEY}"
        h["HTTP-Referer"] = "https://github.com/Yarmageddon/telegram-bot-sbp"
        h["X-Title"] = "Telegram SBP Agents"
    elif OPENAI_API_KEY:
        h["Authorization"] = f"Bearer {OPENAI_API_KEY}"
    return h


# ═══════════════════════════════════════════════════════════════
# ВЫЗОВ LLM
# ═══════════════════════════════════════════════════════════════
# Автокоррекция префикса модели под провайдера
model = LLM_MODEL

model = LLM_MODEL
logger.info(f"[ROUTER] Использую модель: {model}")
    
async def _call_llm(
    messages: list[dict],
    temperature: float = 0.7,
    tools: Optional[list[dict]] = None,
) -> dict:
    """Низкоуровневый вызов LLM API."""
    payload: dict = {
        "model": model,              
        "messages": messages,
        "temperature": temperature,
    }

    if tools:
        payload["tools"] = tools
        if SEND_TOOL_CHOICE:
            payload["tool_choice"] = "auto"

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        r = await client.post(LLM_API_URL, headers=_headers(), json=payload)

        # Если 400 и были tools — попробуем без инструментов
        if r.status_code == 400 and tools:
            logger.warning(
                f"[ROUTER] LLM вернул 400 с tools. Пробуем без инструментов. "
                f"Ответ: {r.text[:400]}"
            )
            payload.pop("tools", None)
            payload.pop("tool_choice", None)
            r = await client.post(LLM_API_URL, headers=_headers(), json=payload)

        if r.status_code >= 400:
            logger.error(
                f"[ROUTER] LLM HTTP {r.status_code}. "
                f"Model={model}. Response: {r.text[:600]}"
            )

        r.raise_for_status()
        return r.json()


# ═══════════════════════════════════════════════════════════════
# AGENTIC LOOP
# ═══════════════════════════════════════════════════════════════

def _safe_parse_args(raw) -> dict:
    """Безопасно распарсить аргументы tool_call."""
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"[ROUTER] Невалидный JSON в аргументах: {raw!r} ({e})")
        return {}


async def _run_loop(messages: list[dict], agent: AgentConfig,
                    user_id: int) -> str:
    """Agentic loop: LLM → tool_calls → execute → LLM → ..."""
    tools = get_tools_for_agent(agent.tools) if agent.tools else None

    for i in range(MAX_TOOL_ITERATIONS):
        logger.debug(f"[ROUTER] {agent.id} iter {i + 1}/{MAX_TOOL_ITERATIONS}")

        resp = await _call_llm(messages, agent.temperature, tools)

        if not resp.get("choices"):
            logger.error(f"[ROUTER] Пустой ответ LLM: {resp}")
            return "⚠️ Пустой ответ модели."

        msg = resp["choices"][0]["message"]
        tool_calls = msg.get("tool_calls") or []

        # Нет вызовов инструментов — это финальный ответ
        if not tool_calls:
            content = (msg.get("content") or "").strip()
            if not content:
                return "⚠️ Модель не дала ответа. Переформулируй запрос."
            return content

        # Добавляем ответ LLM с tool_calls в историю
        messages.append({
            "role": "assistant",
            "content": msg.get("content"),
            "tool_calls": tool_calls,
        })

        # Выполняем каждый вызов
        for tc in tool_calls:
            name = tc["function"]["name"]
            args = _safe_parse_args(tc["function"].get("arguments"))

            logger.info(f"[ROUTER] 🔧 {name}({args})")
            result = await execute_tool(name, user_id=user_id, **args)

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

    # Превысили лимит итераций — финальный вызов без tools
    logger.warning(f"[ROUTER] Лимит итераций ({MAX_TOOL_ITERATIONS}) исчерпан")
    try:
        final = await _call_llm(messages, agent.temperature, tools=None)
        return (
            final["choices"][0]["message"].get("content")
            or "⚠️ Слишком много шагов."
        )
    except Exception as e:
        logger.error(f"[ROUTER] Финальный вызов упал: {e}")
        return "⚠️ Не удалось завершить задачу."


# ═══════════════════════════════════════════════════════════════
# ПУБЛИЧНЫЙ API
# ═══════════════════════════════════════════════════════════════

async def route_to_agent(
    user_message: str,
    agent_id: str,
    user_id: int,
    context: Optional[list[dict]] = None,
) -> str:
    """Главная функция. Работает для всех 16 агентов."""
    agent = get_agent(agent_id)
    if not agent:
        return f"⚠️ Агент '{agent_id}' не найден."
    if not agent.is_available:
        return f"⚠️ Агент «{agent.name}» недоступен."

    if not is_llm_configured():
        return _fallback(agent, user_message)

    messages: list[dict] = [
        {"role": "system", "content": agent.system_prompt},
    ]
    if context:
        for m in context[-20:]:
            if m.get("role") in ("user", "assistant") and m.get("content"):
                messages.append({"role": m["role"], "content": m["content"]})

    messages.append({"role": "user", "content": user_message})

    try:
        return await _run_loop(messages, agent, user_id)

    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        body = e.response.text[:300]
        logger.error(f"[ROUTER] HTTP {code} для {agent.id}: {body}")

        if code == 401:
            return "⚠️ Ошибка авторизации LLM. Проверь API-ключ."
        if code == 402:
            return "⚠️ Закончился баланс у LLM-провайдера."
        if code == 429:
            return "⚠️ Слишком много запросов. Подожди немного."
        if code == 400:
            return (
                "⚠️ Модель отклонила запрос (400).\n"
                "Попробуй переформулировать или смени модель."
            )
        return f"⚠️ Ошибка LLM ({code}). Подробности — в логах Railway."

    except httpx.TimeoutException:
        return "⏱️ Модель не ответила вовремя. Попробуй ещё раз."

    except Exception as e:
        logger.exception(f"[ROUTER] Неожиданная ошибка: {e}")
        return f"⚠️ Ошибка: {type(e).__name__}."


def _fallback(agent: AgentConfig, user_message: str) -> str:
    """Демо-режим без API-ключа."""
    tools = (
        "\n\n🛠 Инструменты:\n" + "\n".join(f"  • `{t}`" for t in agent.tools)
    ) if agent.tools else ""
    return (
        f"{agent.emoji} *{agent.name}* на связи!\n\n"
        f"_{agent.description}_\n\n"
        f"📝 Ты сказал: «{user_message}»{tools}\n\n"
        f"⚙️ _API-ключ LLM не настроен — работаю в демо-режиме._"
    )


# ═══════════════════════════════════════════════════════════════
# ОТЛАДКА
# ═══════════════════════════════════════════════════════════════

async def preview_agent(agent_id: str) -> dict:
    """Что «видит» агент: промпт, инструменты, схемы."""
    agent = get_agent(agent_id)
    if not agent:
        return {"status": "error", "message": "Агент не найден"}
    schemas = get_tools_for_agent(agent.tools)
    return {
        "status": "ok",
        "agent": {
            "id": agent.id, "name": agent.name, "emoji": agent.emoji,
            "category": agent.category, "temperature": agent.temperature,
        },
        "system_prompt_length": len(agent.system_prompt),
        "tools_declared": agent.tools,
        "tools_available": [s["function"]["name"] for s in schemas],
        "tools_missing": [
            t for t in agent.tools
            if t not in [s["function"]["name"] for s in schemas]
        ],
    }


async def healthcheck() -> dict:
    """Проверить LLM минимальным запросом."""
    info = get_llm_info()
    if not info["configured"]:
        return {"status": "disabled", "reason": "no_api_key", **info}
    try:
        r = await _call_llm([{"role": "user", "content": "ping"}], 0.0)
        return {
            "status": "ok",
            "response_preview": r["choices"][0]["message"].get("content", "")[:50],
            **info,
        }
    except Exception as e:
        return {"status": "error", "error": str(e), **info}


# ═══════════════════════════════════════════════════════════════
# САМОПРОВЕРКА
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import asyncio
    from agents import AGENTS

    async def _test():
        info = get_llm_info()
        print("═══ Agent Router — проверка 16 агентов ═══\n")
        print(f"LLM: {info['provider']} / {info['model']} "
              f"({'✅' if info['configured'] else '❌ демо'})")
        print(f"tool_choice отправляется: {info['send_tool_choice']}\n")

        broken = 0
        for aid in AGENTS:
            p = await preview_agent(aid)
            a = p["agent"]
            mark = "✅" if not p["tools_missing"] else "⚠️"
            print(f"{mark} {a['emoji']} {a['name']:22s} "
                  f"tools={len(p['tools_available'])}/{len(p['tools_declared'])}")
            if p["tools_missing"]:
                print(f"    ❌ нет схем: {p['tools_missing']}")
                broken += 1

        print(f"\n{'✅ Всё ок' if not broken else f'⚠️ Проблем: {broken}'}")

        if info["configured"]:
            print("\n── Демо-запрос (weather) ──")
            ans = await route_to_agent("Какая погода в Москве?", "weather", 12345)
            print(ans[:400])

    asyncio.run(_test())
