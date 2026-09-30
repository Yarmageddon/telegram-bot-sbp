"""
tools.py — Реестр инструментов для 16 агентов.

Всего: 49 инструментов, разбитых по категориям.
Каждый — async-функция, возвращающая dict со status.
"""

import json
import logging
import uuid
import inspect
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# MOCK-ХРАНИЛИЩЕ
# ═══════════════════════════════════════════════════════════════

_MOCK_DB: dict[str, dict] = {
    "reminders": {}, "tasks": {}, "subscriptions": {},
    "cleaning_tasks": {}, "family_tasks": {}, "birthdays": {},
    "emails": {}, "meals": {}, "water": {}, "moods": {},
    "plants": {}, "drafts": {},
}

def _store(name: str, user_id: int) -> list:
    s = _MOCK_DB.setdefault(name, {})
    return s.setdefault(str(user_id), [])

def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ═══════════════════════════════════════════════════════════════
# 1. НАПОМИНАНИЯ (агенты: reminder, nutrition)
# ═══════════════════════════════════════════════════════════════

async def create_reminder(user_id: int, text: str, when: str,
                          repeat: Optional[str] = None) -> dict:
    r = {"id": _new_id("rem"), "text": text, "when": when,
         "repeat": repeat, "status": "active", "created_at": _now()}
    _store("reminders", user_id).append(r)
    return {"status": "ok", "reminder_id": r["id"],
            "message": f"Напоминание «{text}» создано на {when}"}

async def list_reminders(user_id: int) -> dict:
    items = _store("reminders", user_id)
    return {"status": "ok", "count": len(items), "reminders": items}

async def delete_reminder(user_id: int, reminder_id: str) -> dict:
    items = _store("reminders", user_id)
    for r in items:
        if r["id"] == reminder_id:
            items.remove(r)
            return {"status": "ok", "message": f"Удалено {reminder_id}"}
    return {"status": "error", "message": "Не найдено"}

async def set_reminder(user_id: int, text: str, when: str) -> dict:
    return await create_reminder(user_id=user_id, text=text, when=when)


# ═══════════════════════════════════════════════════════════════
# 2. ЗАДАЧИ (агенты: task_manager, daily_planner)
# ═══════════════════════════════════════════════════════════════

async def create_task(user_id: int, title: str, deadline: Optional[str] = None,
                      priority: str = "medium", steps: Optional[list] = None) -> dict:
    t = {"id": _new_id("task"), "title": title, "deadline": deadline,
         "priority": priority, "steps": steps or [], "status": "active",
         "created_at": _now()}
    _store("tasks", user_id).append(t)
    return {"status": "ok", "task_id": t["id"],
            "message": f"Задача «{title}» добавлена ({priority})"}

async def list_tasks(user_id: int, filter_status: str = "active") -> dict:
    items = _store("tasks", user_id)
    if filter_status != "all":
        items = [t for t in items if t.get("status") == filter_status]
    order = {"high": 0, "medium": 1, "low": 2}
    items = sorted(items, key=lambda t: order.get(t.get("priority", "medium"), 1))
    return {"status": "ok", "count": len(items), "tasks": items}

async def update_task(user_id: int, task_id: str, **kwargs) -> dict:
    for t in _store("tasks", user_id):
        if t["id"] == task_id:
            t.update({k: v for k, v in kwargs.items() if v is not None})
            return {"status": "ok", "task": t}
    return {"status": "error", "message": "Не найдено"}

async def delete_task(user_id: int, task_id: str) -> dict:
    items = _store("tasks", user_id)
    for t in items:
        if t["id"] == task_id:
            items.remove(t)
            return {"status": "ok", "message": "Удалено"}
    return {"status": "error", "message": "Не найдено"}


# ═══════════════════════════════════════════════════════════════
# 3. ПОДПИСКИ (агент: subscription)
# ═══════════════════════════════════════════════════════════════

async def add_subscription(user_id: int, name: str, amount: float,
                           period: str = "monthly",
                           next_charge_date: Optional[str] = None) -> dict:
    s = {"id": _new_id("sub"), "name": name, "amount": amount, "currency": "RUB",
         "period": period, "next_charge_date": next_charge_date,
         "status": "active", "created_at": _now()}
    _store("subscriptions", user_id).append(s)
    return {"status": "ok", "subscription_id": s["id"],
            "message": f"Подписка «{name}»: {amount} ₽/{period}"}

async def list_subscriptions(user_id: int) -> dict:
    items = _store("subscriptions", user_id)
    total = sum(s["amount"] for s in items if s.get("status") == "active")
    return {"status": "ok", "count": len(items),
            "total_monthly": total, "subscriptions": items}

async def cancel_subscription(user_id: int, subscription_id: str) -> dict:
    for s in _store("subscriptions", user_id):
        if s["id"] == subscription_id:
            s["status"] = "cancelled"
            return {"status": "ok", "message": "Отменено"}
    return {"status": "error", "message": "Не найдено"}

async def get_subscription_summary(user_id: int) -> dict:
    items = [s for s in _store("subscriptions", user_id) if s.get("status") == "active"]
    total = sum(s["amount"] for s in items)
    return {"status": "ok", "active_count": len(items),
            "monthly_total": total, "yearly_total": total * 12}


# ═══════════════════════════════════════════════════════════════
# 4. УБОРКА (агент: cleaning)
# ═══════════════════════════════════════════════════════════════

async def create_cleaning_task(user_id: int, title: str,
                               frequency: str = "weekly",
                               next_date: Optional[str] = None) -> dict:
    t = {"id": _new_id("clean"), "title": title, "frequency": frequency,
         "next_date": next_date, "status": "active", "created_at": _now()}
    _store("cleaning_tasks", user_id).append(t)
    return {"status": "ok", "task_id": t["id"],
            "message": f"Уборка «{title}» ({frequency})"}

async def list_cleaning_tasks(user_id: int) -> dict:
    items = _store("cleaning_tasks", user_id)
    return {"status": "ok", "count": len(items), "tasks": items}

async def complete_task(user_id: int, task_id: str) -> dict:
    for store in ("cleaning_tasks", "family_tasks", "tasks"):
        for t in _store(store, user_id):
            if t["id"] == task_id:
                t["status"] = "completed"
                t["completed_at"] = _now()
                return {"status": "ok", "message": "Выполнено! 🎉"}
    return {"status": "error", "message": "Не найдено"}


# ═══════════════════════════════════════════════════════════════
# 5. СЕМЬЯ (агент: family)
# ═══════════════════════════════════════════════════════════════

async def create_family_task(user_id: int, title: str, assignee: str,
                             deadline: Optional[str] = None) -> dict:
    t = {"id": _new_id("fam"), "title": title, "assignee": assignee,
         "deadline": deadline, "status": "active", "created_at": _now()}
    _store("family_tasks", user_id).append(t)
    return {"status": "ok", "task_id": t["id"],
            "message": f"«{title}» назначена на {assignee}"}

async def list_family_tasks(user_id: int) -> dict:
    items = _store("family_tasks", user_id)
    by_assignee: dict[str, list] = {}
    for t in items:
        by_assignee.setdefault(t["assignee"], []).append(t)
    return {"status": "ok", "count": len(items), "by_assignee": by_assignee}

async def assign_task(user_id: int, task_id: str, assignee: str) -> dict:
    for t in _store("family_tasks", user_id):
        if t["id"] == task_id:
            t["assignee"] = assignee
            return {"status": "ok", "message": f"Переназначено на {assignee}"}
    return {"status": "error", "message": "Не найдено"}


# ═══════════════════════════════════════════════════════════════
# 6. ПОГОДА (агенты: weather, garden, daily_planner)
# ═══════════════════════════════════════════════════════════════

async def get_weather(location: str) -> dict:
    return {"status": "ok", "location": location,
            "temperature": "+12", "feels_like": "+10",
            "condition": "облачно", "humidity": "72%", "wind": "3 м/с",
            "advice": "Возьми зонт, днём обещают дождь.",
            "updated_at": _now()}

async def get_forecast(location: str, days: int = 3) -> dict:
    today = datetime.now()
    forecast = [{
        "date": (today + timedelta(days=i)).strftime("%Y-%m-%d"),
        "weekday": (today + timedelta(days=i)).strftime("%A"),
        "temp_day": f"+{10+i}", "temp_night": f"+{2+i}",
        "condition": ["ясно", "облачно", "дождь"][i % 3],
    } for i in range(min(days, 14))]
    return {"status": "ok", "location": location, "forecast": forecast}


# ═══════════════════════════════════════════════════════════════
# 7. КАЛЕНДАРЬ И ДНИ РОЖДЕНИЯ (агент: calendar_birthday)
# ═══════════════════════════════════════════════════════════════

async def get_calendar(user_id: int, date: Optional[str] = None) -> dict:
    return {"status": "ok",
            "date": date or datetime.now().strftime("%Y-%m-%d"),
            "events": [
                {"time": "11:00", "title": "Встреча с командой", "duration": "1ч"},
                {"time": "15:30", "title": "Созвон с клиентом", "duration": "30м"},
            ]}

async def list_birthdays(user_id: int, days_ahead: int = 7) -> dict:
    items = _store("birthdays", user_id)
    return {"status": "ok", "count": len(items), "birthdays": items}

async def add_birthday(user_id: int, name: str, date: str) -> dict:
    bd = {"id": _new_id("bd"), "name": name, "date": date, "created_at": _now()}
    _store("birthdays", user_id).append(bd)
    return {"status": "ok", "birthday_id": bd["id"],
            "message": f"ДР {name} ({date}) добавлен"}


# ═══════════════════════════════════════════════════════════════
# 8. ПОЧТА (агент: email_triage)
# ═══════════════════════════════════════════════════════════════

async def get_emails(user_id: int, filter_unread: bool = True) -> dict:
    return {"status": "ok", "total": 12, "unread": 5, "urgent": 2,
            "emails": [
                {"id": "em_001", "from": "boss@company.com",
                 "subject": "Правки в отчёте", "priority": "high", "received": "10:23"},
                {"id": "em_002", "from": "client@corp.ru",
                 "subject": "Договор на согласование", "priority": "high", "received": "09:15"},
            ]}

async def draft_reply(user_id: int, email_id: str, tone: str = "neutral") -> dict:
    d = {"id": _new_id("draft"), "email_id": email_id, "tone": tone,
         "body": "Здравствуйте! Спасибо за письмо...", "created_at": _now()}
    _store("drafts", user_id).append(d)
    return {"status": "ok", "draft_id": d["id"], "message": "Черновик готов", "draft": d}

async def send_email(user_id: int, to: str, subject: str, body: str) -> dict:
    return {"status": "ok", "message": f"Письмо «{subject}» отправлено на {to}"}

async def mark_as_read(user_id: int, email_id: str) -> dict:
    return {"status": "ok", "message": f"{email_id} помечено прочитанным"}


# ═══════════════════════════════════════════════════════════════
# 9. ПИТАНИЕ (агент: nutrition)
# ═══════════════════════════════════════════════════════════════

async def log_meal(user_id: int, description: str, meal_type: str = "lunch",
                   calories: Optional[int] = None) -> dict:
    m = {"id": _new_id("meal"), "description": description,
         "meal_type": meal_type, "calories": calories, "logged_at": _now()}
    _store("meals", user_id).append(m)
    return {"status": "ok", "meal_id": m["id"], "message": f"Записал: {description}"}

async def log_water(user_id: int, amount_ml: int = 250) -> dict:
    _store("water", user_id).append(
        {"id": _new_id("water"), "amount_ml": amount_ml, "logged_at": _now()}
    )
    total = sum(w["amount_ml"] for w in _store("water", user_id))
    return {"status": "ok", "total_ml": total,
            "message": f"+{amount_ml}мл. Всего: {total}мл"}

async def get_nutrition_summary(user_id: int) -> dict:
    meals = _store("meals", user_id)
    water = sum(w["amount_ml"] for w in _store("water", user_id))
    cal = sum(m.get("calories") or 0 for m in meals)
    return {"status": "ok", "meals_count": len(meals), "total_calories": cal,
            "water_ml": water, "water_goal_ml": 2000}


# ═══════════════════════════════════════════════════════════════
# 10. ПСИХИКА (агент: mental_health)
# ═══════════════════════════════════════════════════════════════

async def log_mood(user_id: int, mood: int, note: Optional[str] = None) -> dict:
    _store("moods", user_id).append(
        {"id": _new_id("mood"), "mood": mood, "note": note, "logged_at": _now()}
    )
    return {"status": "ok", "message": f"Настроение {mood}/10 записано"}

async def get_mood_history(user_id: int, days: int = 7) -> dict:
    items = _store("moods", user_id)
    avg = sum(m["mood"] for m in items) / len(items) if items else 0
    return {"status": "ok", "entries": items[-days:], "average": round(avg, 1)}

async def suggest_practice(user_id: int, state: str = "neutral") -> dict:
    practices = {
        "anxious": {"name": "Дыхание 4-7-8", "duration": "2 мин",
                    "steps": "Вдох 4с — задержка 7с — выдох 8с. 4 раза."},
        "low": {"name": "Дневник благодарности", "duration": "5 мин",
                "steps": "Запиши 3 вещи, за которые ты благодарен."},
        "neutral": {"name": "Заземление 5-4-3-2-1", "duration": "3 мин",
                    "steps": "5 видишь, 4 слышишь, 3 трогаешь, 2 запах, 1 вкус."},
    }
    return {"status": "ok", "practice": practices.get(state, practices["neutral"])}


# ═══════════════════════════════════════════════════════════════
# 11. ЮРИСТ (агент: lawyer)
# ═══════════════════════════════════════════════════════════════

async def search_legal_base(query: str, area: str = "general") -> dict:
    return {"status": "ok", "query": query,
            "results": [{"title": "ГК РФ ст. 309", "snippet": "Обязательства..."}],
            "disclaimer": "Справочно, не консультация."}

async def analyze_document(document_text: str, doc_type: str = "contract") -> dict:
    return {"status": "ok", "doc_type": doc_type,
            "key_points": ["Срок: 12 месяцев", "Штраф: 0,5%/день"],
            "risks": [{"level": "high", "text": "Штраф выше рыночного"}],
            "disclaimer": "Шаблонный анализ. Проверьте с юристом."}

async def set_legal_deadline(user_id: int, title: str, date: str,
                             description: Optional[str] = None) -> dict:
    d = {"id": _new_id("legal"), "title": title, "date": date,
         "description": description, "created_at": _now()}
    _store("reminders", user_id).append(
        {"id": d["id"], "text": f"⚖️ {title}", "when": date, "status": "active"}
    )
    return {"status": "ok", "deadline_id": d["id"], "message": f"Дедлайн «{title}» на {date}"}


# ═══════════════════════════════════════════════════════════════
# 12. АНАЛИТИК (агент: analyst)
# ═══════════════════════════════════════════════════════════════

async def query_data(source: str, query: str, filters: Optional[dict] = None) -> dict:
    return {"status": "ok", "source": source, "rows": 150,
            "columns": ["date", "revenue", "orders", "conversion"],
            "sample": [{"date": "2026-09-28", "revenue": 125000, "orders": 47}]}

async def build_report(data: dict, report_type: str = "summary") -> dict:
    return {"status": "ok", "report_type": report_type,
            "summary": "Продажи: +12% за неделю.",
            "insights": ["Драйвер — новый канал", "Конверсия упала на этапе оплаты"]}

async def find_anomalies(data: dict, sensitivity: str = "medium") -> dict:
    return {"status": "ok", "anomalies": [
        {"date": "2026-09-29", "metric": "conversion",
         "value": 0.031, "expected": 0.042, "deviation": "-26%"}]}

async def visualize(data: dict, chart_type: str = "line", title: str = "") -> dict:
    return {"status": "ok", "chart_type": chart_type, "title": title,
            "image_url": "https://example.com/chart.png", "message": "График построен"}


# ═══════════════════════════════════════════════════════════════
# 13. ПЕРЕВОД (агент: translator)
# ═══════════════════════════════════════════════════════════════

async def translate_text(text: str, target_lang: str,
                         source_lang: str = "auto", tone: str = "neutral") -> dict:
    return {"status": "ok", "source_lang": source_lang, "target_lang": target_lang,
            "translation": f"[Перевод на {target_lang}]: {text}",
            "note": "Заглушка. Подключите DeepL или Google Translate."}

async def lookup_dictionary(word: str, lang: str = "en") -> dict:
    return {"status": "ok", "word": word,
            "definitions": [f"Значение «{word}» (заглушка)"], "synonyms": []}

async def explain_idiom(idiom: str, lang: str = "en") -> dict:
    return {"status": "ok", "idiom": idiom,
            "meaning": "Значение идиомы (заглушка)",
            "equivalent": "Аналог в русском (заглушка)"}


# ═══════════════════════════════════════════════════════════════
# 14. КОПИРАЙТИНГ (агент: copywriter)
# ═══════════════════════════════════════════════════════════════

async def check_style(text: str, style: str = "neutral") -> dict:
    return {"status": "ok", "readability": "8/10",
            "issues": [{"type": "cliche", "text": "канцелярит"}],
            "suggestions": ["Заменить пассив на актив", "Сократить предложения"]}

async def generate_headlines(topic: str, count: int = 3,
                             style: str = "engaging") -> dict:
    return {"status": "ok",
            "headlines": [f"Вариант {i+1}: {topic}" for i in range(count)]}

async def save_draft(user_id: int, title: str, body: str) -> dict:
    d = {"id": _new_id("txt"), "title": title, "body": body, "created_at": _now()}
    _store("drafts", user_id).append(d)
    return {"status": "ok", "draft_id": d["id"], "message": f"Черновик «{title}» сохранён"}


# ═══════════════════════════════════════════════════════════════
# 15. САД (агент: garden)
# ═══════════════════════════════════════════════════════════════

async def add_plant(user_id: int, name: str, species: Optional[str] = None,
                    watering_days: int = 3) -> dict:
    p = {"id": _new_id("plant"), "name": name, "species": species,
         "watering_days": watering_days, "last_watered": None, "created_at": _now()}
    _store("plants", user_id).append(p)
    return {"status": "ok", "plant_id": p["id"],
            "message": f"«{name}» добавлено (полив каждые {watering_days} дн.)"}

async def list_plants(user_id: int) -> dict:
    items = _store("plants", user_id)
    return {"status": "ok", "count": len(items), "plants": items}

async def watering_schedule(user_id: int) -> dict:
    plants = _store("plants", user_id)
    return {"status": "ok", "schedule": [
        {"plant": p["name"],
         "next_watering": "завтра" if i % 2 == 0 else "через 2 дня"}
        for i, p in enumerate(plants)
    ]}


# ═══════════════════════════════════════════════════════════════
# РЕЕСТР ИНСТРУМЕНТОВ
# ═══════════════════════════════════════════════════════════════

TOOL_REGISTRY: dict[str, callable] = {
    # Напоминания
    "create_reminder": create_reminder, "list_reminders": list_reminders,
    "delete_reminder": delete_reminder, "set_reminder": set_reminder,
    # Задачи
    "create_task": create_task, "list_tasks": list_tasks,
    "update_task": update_task, "delete_task": delete_task,
    # Подписки
    "add_subscription": add_subscription, "list_subscriptions": list_subscriptions,
    "cancel_subscription": cancel_subscription,
    "get_subscription_summary": get_subscription_summary,
    # Уборка
    "create_cleaning_task": create_cleaning_task,
    "list_cleaning_tasks": list_cleaning_tasks, "complete_task": complete_task,
    # Семья
    "create_family_task": create_family_task,
    "list_family_tasks": list_family_tasks, "assign_task": assign_task,
    # Погода
    "get_weather": get_weather, "get_forecast": get_forecast,
    # Календарь
    "get_calendar": get_calendar, "list_birthdays": list_birthdays,
    "add_birthday": add_birthday,
    # Почта
    "get_emails": get_emails, "draft_reply": draft_reply,
    "send_email": send_email, "mark_as_read": mark_as_read,
    # Питание
    "log_meal": log_meal, "log_water": log_water,
    "get_nutrition_summary": get_nutrition_summary,
    # Психика
    "log_mood": log_mood, "get_mood_history": get_mood_history,
    "suggest_practice": suggest_practice,
    # Юрист
    "search_legal_base": search_legal_base,
    "analyze_document": analyze_document, "set_legal_deadline": set_legal_deadline,
    # Аналитик
    "query_data": query_data, "build_report": build_report,
    "find_anomalies": find_anomalies, "visualize": visualize,
    # Переводчик
    "translate_text": translate_text, "lookup_dictionary": lookup_dictionary,
    "explain_idiom": explain_idiom,
    # Копирайтер
    "check_style": check_style, "generate_headlines": generate_headlines,
    "save_draft": save_draft,
    # Сад
    "add_plant": add_plant, "list_plants": list_plants,
    "watering_schedule": watering_schedule,
}


# ═══════════════════════════════════════════════════════════════
# JSON-СХЕМЫ ДЛЯ FUNCTION CALLING
# ═══════════════════════════════════════════════════════════════

TOOL_SCHEMAS: dict[str, dict] = {
    "create_reminder": {"type": "function", "function": {
        "name": "create_reminder", "description": "Создать напоминание",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string"}, "when": {"type": "string"},
            "repeat": {"type": "string", "enum": ["daily", "weekly", "monthly"]}},
            "required": ["text", "when"]}}},
    "list_reminders": {"type": "function", "function": {
        "name": "list_reminders", "description": "Список напоминаний",
        "parameters": {"type": "object", "properties": {}}}},
    "delete_reminder": {"type": "function", "function": {
        "name": "delete_reminder", "description": "Удалить напоминание",
        "parameters": {"type": "object", "properties": {
            "reminder_id": {"type": "string"}}, "required": ["reminder_id"]}}},
    "set_reminder": {"type": "function", "function": {
        "name": "set_reminder", "description": "Установить напоминание",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string"}, "when": {"type": "string"}},
            "required": ["text", "when"]}}},

    "create_task": {"type": "function", "function": {
        "name": "create_task", "description": "Создать задачу",
        "parameters": {"type": "object", "properties": {
            "title": {"type": "string"}, "deadline": {"type": "string"},
            "priority": {"type": "string", "enum": ["low", "medium", "high"]},
            "steps": {"type": "array", "items": {"type": "string"}}},
            "required": ["title"]}}},
    "list_tasks": {"type": "function", "function": {
        "name": "list_tasks", "description": "Список задач",
        "parameters": {"type": "object", "properties": {
            "filter_status": {"type": "string",
                              "enum": ["active", "completed", "all"]}}}}},
    "update_task": {"type": "function", "function": {
        "name": "update_task", "description": "Обновить задачу",
        "parameters": {"type": "object", "properties": {
            "task_id": {"type": "string"}, "title": {"type": "string"},
            "deadline": {"type": "string"}, "priority": {"type": "string"},
            "status": {"type": "string"}}, "required": ["task_id"]}}},
    "delete_task": {"type": "function", "function": {
        "name": "delete_task", "description": "Удалить задачу",
        "parameters": {"type": "object", "properties": {
            "task_id": {"type": "string"}}, "required": ["task_id"]}}},

    "add_subscription": {"type": "function", "function": {
        "name": "add_subscription", "description": "Добавить подписку",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"}, "amount": {"type": "number"},
            "period": {"type": "string",
                       "enum": ["monthly", "yearly", "weekly"]},
            "next_charge_date": {"type": "string"}},
            "required": ["name", "amount"]}}},
    "list_subscriptions": {"type": "function", "function": {
        "name": "list_subscriptions", "description": "Список подписок",
        "parameters": {"type": "object", "properties": {}}}},
    "cancel_subscription": {"type": "function", "function": {
        "name": "cancel_subscription", "description": "Отменить подписку",
        "parameters": {"type": "object", "properties": {
            "subscription_id": {"type": "string"}},
            "required": ["subscription_id"]}}},
    "get_subscription_summary": {"type": "function", "function": {
        "name": "get_subscription_summary", "description": "Сводка по подпискам",
        "parameters": {"type": "object", "properties": {}}}},

    "create_cleaning_task": {"type": "function", "function": {
        "name": "create_cleaning_task", "description": "Создать задачу уборки",
        "parameters": {"type": "object", "properties": {
            "title": {"type": "string"},
            "frequency": {"type": "string",
                          "enum": ["daily", "weekly", "monthly", "seasonal"]},
            "next_date": {"type": "string"}}, "required": ["title"]}}},
    "list_cleaning_tasks": {"type": "function", "function": {
        "name": "list_cleaning_tasks", "description": "Список задач уборки",
        "parameters": {"type": "object", "properties": {}}}},
    "complete_task": {"type": "function", "function": {
        "name": "complete_task", "description": "Отметить выполненной",
        "parameters": {"type": "object", "properties": {
            "task_id": {"type": "string"}}, "required": ["task_id"]}}},

    "create_family_task": {"type": "function", "function": {
        "name": "create_family_task", "description": "Семейная задача",
        "parameters": {"type": "object", "properties": {
            "title": {"type": "string"}, "assignee": {"type": "string"},
            "deadline": {"type": "string"}},
            "required": ["title", "assignee"]}}},
    "list_family_tasks": {"type": "function", "function": {
        "name": "list_family_tasks", "description": "Семейные задачи",
        "parameters": {"type": "object", "properties": {}}}},
    "assign_task": {"type": "function", "function": {
        "name": "assign_task", "description": "Переназначить задачу",
        "parameters": {"type": "object", "properties": {
            "task_id": {"type": "string"}, "assignee": {"type": "string"}},
            "required": ["task_id", "assignee"]}}},

    "get_weather": {"type": "function", "function": {
        "name": "get_weather", "description": "Текущая погода",
        "parameters": {"type": "object", "properties": {
            "location": {"type": "string"}}, "required": ["location"]}}},
    "get_forecast": {"type": "function", "function": {
        "name": "get_forecast", "description": "Прогноз погоды",
        "parameters": {"type": "object", "properties": {
            "location": {"type": "string"},
            "days": {"type": "integer", "minimum": 1, "maximum": 14}},
            "required": ["location"]}}},

    "get_calendar": {"type": "function", "function": {
        "name": "get_calendar", "description": "События календаря",
        "parameters": {"type": "object", "properties": {
            "date": {"type": "string"}}}}},
    "list_birthdays": {"type": "function", "function": {
        "name": "list_birthdays", "description": "Дни рождения",
        "parameters": {"type": "object", "properties": {
            "days_ahead": {"type": "integer"}}}}},
    "add_birthday": {"type": "function", "function": {
        "name": "add_birthday", "description": "Добавить ДР",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"}, "date": {"type": "string"}},
            "required": ["name", "date"]}}},

    "get_emails": {"type": "function", "function": {
        "name": "get_emails", "description": "Список писем",
        "parameters": {"type": "object", "properties": {
            "filter_unread": {"type": "boolean"}}}}},
    "draft_reply": {"type": "function", "function": {
        "name": "draft_reply", "description": "Черновик ответа",
        "parameters": {"type": "object", "properties": {
            "email_id": {"type": "string"},
            "tone": {"type": "string",
                     "enum": ["neutral", "formal", "friendly"]}},
            "required": ["email_id"]}}},
    "send_email": {"type": "function", "function": {
        "name": "send_email", "description": "Отправить письмо",
        "parameters": {"type": "object", "properties": {
            "to": {"type": "string"}, "subject": {"type": "string"},
            "body": {"type": "string"}},
            "required": ["to", "subject", "body"]}}},
    "mark_as_read": {"type": "function", "function": {
        "name": "mark_as_read", "description": "Прочитано",
        "parameters": {"type": "object", "properties": {
            "email_id": {"type": "string"}}, "required": ["email_id"]}}},

    "log_meal": {"type": "function", "function": {
        "name": "log_meal", "description": "Записать еду",
        "parameters": {"type": "object", "properties": {
            "description": {"type": "string"},
            "meal_type": {"type": "string",
                          "enum": ["breakfast", "lunch", "dinner", "snack"]},
            "calories": {"type": "integer"}}, "required": ["description"]}}},
    "log_water": {"type": "function", "function": {
        "name": "log_water", "description": "Записать воду",
        "parameters": {"type": "object", "properties": {
            "amount_ml": {"type": "integer"}}}}},
    "get_nutrition_summary": {"type": "function", "function": {
        "name": "get_nutrition_summary", "description": "Сводка по питанию",
        "parameters": {"type": "object", "properties": {}}}},

    "log_mood": {"type": "function", "function": {
        "name": "log_mood", "description": "Записать настроение 1-10",
        "parameters": {"type": "object", "properties": {
            "mood": {"type": "integer", "minimum": 1, "maximum": 10},
            "note": {"type": "string"}}, "required": ["mood"]}}},
    "get_mood_history": {"type": "function", "function": {
        "name": "get_mood_history", "description": "История настроения",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer"}}}}},
    "suggest_practice": {"type": "function", "function": {
        "name": "suggest_practice", "description": "Практика по состоянию",
        "parameters": {"type": "object", "properties": {
            "state": {"type": "string",
                      "enum": ["anxious", "low", "neutral"]}}}}},

    "search_legal_base": {"type": "function", "function": {
        "name": "search_legal_base", "description": "Поиск в правовой базе",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}, "area": {"type": "string"}},
            "required": ["query"]}}},
    "analyze_document": {"type": "function", "function": {
        "name": "analyze_document", "description": "Анализ документа",
        "parameters": {"type": "object", "properties": {
            "document_text": {"type": "string"},
            "doc_type": {"type": "string",
                         "enum": ["contract", "claim", "letter"]}},
            "required": ["document_text"]}}},
    "set_legal_deadline": {"type": "function", "function": {
        "name": "set_legal_deadline", "description": "Юр. дедлайн",
        "parameters": {"type": "object", "properties": {
            "title": {"type": "string"}, "date": {"type": "string"},
            "description": {"type": "string"}},
            "required": ["title", "date"]}}},

    "query_data": {"type": "function", "function": {
        "name": "query_data", "description": "Запрос данных",
        "parameters": {"type": "object", "properties": {
            "source": {"type": "string"}, "query": {"type": "string"},
            "filters": {"type": "object"}},
            "required": ["source", "query"]}}},
    "build_report": {"type": "function", "function": {
        "name": "build_report", "description": "Построить отчёт",
        "parameters": {"type": "object", "properties": {
            "data": {"type": "object"},
            "report_type": {"type": "string",
                            "enum": ["summary", "detailed", "executive"]}},
            "required": ["data"]}}},
    "find_anomalies": {"type": "function", "function": {
        "name": "find_anomalies", "description": "Найти аномалии",
        "parameters": {"type": "object", "properties": {
            "data": {"type": "object"},
            "sensitivity": {"type": "string",
                            "enum": ["low", "medium", "high"]}},
            "required": ["data"]}}},
    "visualize": {"type": "function", "function": {
        "name": "visualize", "description": "Построить график",
        "parameters": {"type": "object", "properties": {
            "data": {"type": "object"},
            "chart_type": {"type": "string",
                           "enum": ["line", "bar", "pie", "scatter"]},
            "title": {"type": "string"}}, "required": ["data"]}}},

    "translate_text": {"type": "function", "function": {
        "name": "translate_text", "description": "Перевести текст",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string"}, "target_lang": {"type": "string"},
            "source_lang": {"type": "string"},
            "tone": {"type": "string",
                     "enum": ["neutral", "formal", "friendly"]}},
            "required": ["text", "target_lang"]}}},
    "lookup_dictionary": {"type": "function", "function": {
        "name": "lookup_dictionary", "description": "Словарь",
        "parameters": {"type": "object", "properties": {
            "word": {"type": "string"}, "lang": {"type": "string"}},
            "required": ["word"]}}},
    "explain_idiom": {"type": "function", "function": {
        "name": "explain_idiom", "description": "Объяснить идиому",
        "parameters": {"type": "object", "properties": {
            "idiom": {"type": "string"}, "lang": {"type": "string"}},
            "required": ["idiom"]}}},

    "check_style": {"type": "function", "function": {
        "name": "check_style", "description": "Проверить стиль",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string"}, "style": {"type": "string"}},
            "required": ["text"]}}},
    "generate_headlines": {"type": "function", "function": {
        "name": "generate_headlines", "description": "Заголовки",
        "parameters": {"type": "object", "properties": {
            "topic": {"type": "string"}, "count": {"type": "integer"},
            "style": {"type": "string"}}, "required": ["topic"]}}},
    "save_draft": {"type": "function", "function": {
        "name": "save_draft", "description": "Сохранить черновик",
        "parameters": {"type": "object", "properties": {
            "title": {"type": "string"}, "body": {"type": "string"}},
            "required": ["title", "body"]}}},

    "add_plant": {"type": "function", "function": {
        "name": "add_plant", "description": "Добавить растение",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"}, "species": {"type": "string"},
            "watering_days": {"type": "integer"}}, "required": ["name"]}}},
    "list_plants": {"type": "function", "function": {
        "name": "list_plants", "description": "Список растений",
        "parameters": {"type": "object", "properties": {}}}},
    "watering_schedule": {"type": "function", "function": {
        "name": "watering_schedule", "description": "Расписание полива",
        "parameters": {"type": "object", "properties": {}}}},
}


def get_tools_for_agent(tool_names: list[str]) -> list[dict]:
    """Схемы инструментов только для конкретного агента."""
    return [TOOL_SCHEMAS[n] for n in tool_names if n in TOOL_SCHEMAS]


# ═══════════════════════════════════════════════════════════════
# ВЫПОЛНЕНИЕ ИНСТРУМЕНТА
# ═══════════════════════════════════════════════════════════════

async def execute_tool(tool_name: str, user_id: int, **kwargs) -> dict:
    """Выполнить инструмент. Автоматически подставит user_id, если нужно."""
    tool = TOOL_REGISTRY.get(tool_name)
    if not tool:
        return {"status": "error", "message": f"Инструмент '{tool_name}' не найден"}
    if "user_id" in inspect.signature(tool).parameters:
        kwargs["user_id"] = user_id
    try:
        return await tool(**kwargs)
    except TypeError as e:
        return {"status": "error", "message": f"Ошибка аргументов: {e}"}
    except Exception as e:
        logger.error(f"[TOOL] {tool_name}: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


# ═══════════════════════════════════════════════════════════════
# САМОПРОВЕРКА
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import asyncio
    from agents import AGENTS

    print(f"✅ Инструментов в реестре: {len(TOOL_REGISTRY)}")
    print(f"✅ Схем function calling: {len(TOOL_SCHEMAS)}\n")

    missing = [(a.id, t) for a in AGENTS.values()
               for t in a.tools if t not in TOOL_REGISTRY]
    if missing:
        print("❌ Отсутствуют:")
        for aid, t in missing:
            print(f"   {aid}.{t}")
    else:
        print("✅ Все инструменты из agents.py есть в TOOL_REGISTRY")

    missing_schemas = [(a.id, t) for a in AGENTS.values()
                       for t in a.tools if t not in TOOL_SCHEMAS]
    if missing_schemas:
        print("❌ Нет схем:")
        for aid, t in missing_schemas:
            print(f"   {aid}.{t}")
    else:
        print("✅ Все инструменты из agents.py имеют схемы")

    # Демо
    async def _demo():
        print("\n── Демо ──")
        r = await execute_tool("create_reminder", user_id=1,
                               text="Позвонить маме", when="завтра 10:00")
        print(f"  {r['message']}")
        r = await execute_tool("get_weather", user_id=1, location="Москва")
        print(f"  {r['location']}: {r['temperature']}, {r['condition']}")
    asyncio.run(_demo())
