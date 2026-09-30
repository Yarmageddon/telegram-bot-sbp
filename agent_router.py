"""
agent_router.py — Роутер запросов между всеми 16 агентами.

Работает с любым агентом из agents.py автоматически:
- берёт system_prompt агента,
- подтягивает нужные схемы из tools.py,
- гоняет agentic loop (LLM ↔ tool calls ↔ LLM),
- возвращает финальный текст.
"""

import os
import json
import logging
from typing import Optional

import httpx

from agents import AgentConfig, get_agent
from tools import execute_tool, get_tools_for_agent

logger = logging.getLogger(__name__)

# ─── Конфиг ─────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

LLM_API_URL = os.getenv(
    "LLM_API_URL",
    "https://openrouter.ai/api/v1/chat/completions" if OPENROUTER_API_KEY
    else "https://api.openai.com/v1/chat/completions",
)
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
MAX_TOOL_ITERATIONS = int(os.getenv("MAX_TOOL_ITERATIONS", "5"))
REQUEST_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))


# ─── Утилиты конфигурации ───────────────────────────────────────

def is_llm_configured() -> bool:
    return bool(OPENAI_API_KEY or OPENROUTER_API_KEY)


def get_llm_info() -> dict:
    provider = "openrouter" if OPENROUTER_API_KEY else (
        "openai" if OPENAI_API_KEY else "none")
    return {"provider": provider, "model": LLM_MODEL,
            "url": LLM_API_URL, "configured": is_llm_configured()}


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if OPENROUTER_API_KEY:
        h["Authorization"] = f"Bearer {OPENROUTER_API_KEY}"
        h["HTTP-Referer"] = "https://github.com/Yarmageddon/telegram-bot-sbp"
        h["X-Title"] = "Telegram SBP Agents"
    elif OPENAI_API_KEY:
        h["Authorization"] = f"Bearer {OPENAI_API_KEY}"
    return h


async def _call_llm(messages: list[dict], temperature: float = 0.7,
                    tools: Optional[list[dict]] = None) -> dict:
    payload = {"model": LLM_MODEL, "messages": messages,
               "temperature": temperature}
   if tools:
    payload["tools"] = tools
    # Некоторые модели не поддерживают tool_choice
    # payload["tool_choice"] = "auto"

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        r = await client.post(LLM_API_URL, headers=_headers(), json=payload)
        r.raise_for_status()
        return r.json()


# ─── Agentic loop ───────────────────────────────────────────────

async def _run_loop(messages: list[dict], agent: AgentConfig,
                    user_id: int) -> str:
    tools = get_tools_for_agent(agent.tools) if agent.tools else None

    for i in range(MAX_TOOL_ITERATIONS):
        logger.debug(f"[ROUTER] {agent.id} iter {i+1}/{MAX_TOOL_ITERATIONS}")

        resp = await _call_llm(messages, agent.temperature, tools)
        if not resp.get("choices"):
            return "⚠️ Пустой ответ модели."

        msg = resp["choices"][0]["message"]
        tool_calls = msg.get("tool_calls") or []

        if not tool_calls:
            return msg.get("content") or "⚠️ Модель не дала ответа."

        # Добавляем ответ LLM с tool_calls в историю
        messages.append({"role": "assistant",
                         "content": msg.get("content"),
                         "tool_calls": tool_calls})

        # Выполняем каждый вызов
       for tc in tool_calls:
    name = tc["function"]["name"]
    args_raw = tc["function"].get("arguments", "{}")
    try:
        args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"Некорректный JSON в аргументах {name}: {args_raw}")
        args = {}
    # ...

            logger.info(f"[ROUTER] 🔧 {name}({args})")
            result = await execute_tool(name, user_id=user_id, **args)

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

    # Лимит итераций — финальный вызов без tools
    try:
        final = await _call_llm(messages, agent.temperature, tools=None)
        return final["choices"][0]["message"].get("content") \
               or "⚠️ Слишком много шагов."
    except Exception as e:
        logger.error(f"[ROUTER] Финал упал: {e}")
        return "⚠️ Не удалось завершить задачу."


# ─── Публичный API ──────────────────────────────────────────────

async def route_to_agent(user_message: str, agent_id: str, user_id: int,
                         context: Optional[list[dict]] = None) -> str:
    """Главная функция. Работает для всех 16 агентов."""
    agent = get_agent(agent_id)
    if not agent:
        return f"⚠️ Агент '{agent_id}' не найден."
    if not agent.is_available:
        return f"⚠️ Агент «{agent.name}» недоступен."

    if not is_llm_configured():
        return _fallback(agent, user_message)

    messages = [{"role": "system", "content": agent.system_prompt}]
    if context:
        for m in context[-20:]:
            if m.get("role") in ("user", "assistant") and m.get("content"):
                messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_message})

    try:
        return await _run_loop(messages, agent, user_id)
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        if code == 401:
            return "⚠️ Ошибка авторизации LLM."
        if code == 429:
            return "⚠️ Слишком много запросов. Подожди."
        return f"⚠️ Ошибка LLM ({code})."
    except httpx.TimeoutException:
        return "⏱️ Модель не ответила вовремя."
    except Exception as e:
        logger.exception(f"[ROUTER] {e}")
        return f"⚠️ Ошибка: {type(e).__name__}."


def _fallback(agent: AgentConfig, user_message: str) -> str:
    """Демо-режим без API."""
    tools = ("\n\n🛠 Инструменты:\n" +
             "\n".join(f"  • `{t}`" for t in agent.tools)) if agent.tools else ""
    return (f"{agent.emoji} *{agent.name}* на связи!\n\n"
            f"_{agent.description}_\n\n"
            f"📝 Ты сказал: «{user_message}»{tools}\n\n"
            f"⚙️ _API-ключ LLM не настроен — работаю в демо-режиме._")


# ─── Отладка ────────────────────────────────────────────────────

async def preview_agent(agent_id: str) -> dict:
    agent = get_agent(agent_id)
    if not agent:
        return {"status": "error", "message": "Агент не найден"}
    schemas = get_tools_for_agent(agent.tools)
    return {
        "status": "ok",
        "agent": {"id": agent.id, "name": agent.name, "emoji": agent.emoji,
                  "category": agent.category, "temperature": agent.temperature},
        "system_prompt_length": len(agent.system_prompt),
        "tools_declared": agent.tools,
        "tools_available": [s["function"]["name"] for s in schemas],
        "tools_missing": [t for t in agent.tools
                          if t not in [s["function"]["name"] for s in schemas]],
    }


async def healthcheck() -> dict:
    info = get_llm_info()
    if not info["configured"]:
        return {"status": "disabled", "reason": "no_api_key", **info}
    try:
        r = await _call_llm([{"role": "user", "content": "ping"}], 0.0)
        return {"status": "ok",
                "response_preview": r["choices"][0]["message"].get("content", "")[:50],
                **info}
    except Exception as e:
        return {"status": "error", "error": str(e), **info}


# ─── Самопроверка ───────────────────────────────────────────────

if __name__ == "__main__":
    import asyncio
    from agents import AGENTS

    async def _test():
        info = get_llm_info()
        print("═══ Agent Router — проверка всех 16 агентов ═══\n")
        print(f"LLM: {info['provider']} / {info['model']} "
              f"({'✅' if info['configured'] else '❌ демо'})\n")

        broken = 0
        for aid in AGENTS:
            p = await preview_agent(aid)
            a = p["agent"]
            mark = "✅" if not p["tools_missing"] else "⚠️"
            print(f"{mark} {a['emoji']} {a['name']:25s} "
                  f"tools={len(p['tools_available'])}/{len(p['tools_declared'])} "
                  f"prompt={p['system_prompt_length']}с")
            if p["tools_missing"]:
                print(f"    ❌ нет схем: {p['tools_missing']}")
                broken += 1

        print(f"\n{'✅ Всё ок' if not broken else f'⚠️ Проблем: {broken}'}")

        if info["configured"]:
            print("\n── Демо-запрос (weather) ──")
            ans = await route_to_agent("Какая погода в Москве?",
                                       "weather", 12345)
            print(ans[:300])

    asyncio.run(_test())
