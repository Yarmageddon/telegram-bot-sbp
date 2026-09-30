"""
tools.py — Реестр инструментов для всех агентов.

Каждый инструмент — это "рука" агента: асинхронная функция, которая
возвращает структурированный dict. Пока заглушки, позже заменим на реальные
вызовы (БД, API погоды, Google Calendar, Gmail и т.д.).

Всего инструментов: 43
Уникальных: 40 (некоторые переиспользуются между агентами)
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# MOCK-ХРАНИЛИЩА (в памяти, для демонстрации)
# ═══════════════════════════════════════════════════════════════

_MOCK_DB: dict[str, dict] = {
    "reminders": {},       # user_id -> list[dict]
    "tasks": {},           # user_id -> list[dict]
    "subscriptions": {},   # user_id -> list[dict]
    "cleaning_tasks": {},  # user_id -> list[dict]
    "family_tasks": {},    # user_id -> list[dict]
    "birthdays": {},       # user_id -> list[dict]
    "emails": {},          # user_id -> list[dict]
    "meals": {},           # user_id -> list[dict]
    "water": {},           # user_id -> list[dict]
    "moods": {},           # user_id -> list[dict]
    "plants": {},          # user_id -> list[dict]
    "drafts": {},          # user_id -> list[dict]
}


def _get_user_store(store_name: str, user_id: int) -> list:
    """Получить список записей пользователя из mock-хранилища."""
    store = _MOCK_DB.setdefault(store_name, {})
    return store.setdefault(str(user_id), [])


def _new_id(prefix: str) -> str:
    """Сгенерировать короткий ID."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _now() -> str:
    """Текущее время в ISO-формате."""
    return datetime.now().isoformat(timespec="seconds")


# ═══════════════════════════════════════════════════════════════
# КАТЕГОРИЯ 1: НАПОМИНАНИЯ (reminder, nutrition, daily_planner)
# ═══════════════════════════════════════════════════════════════

async def create_reminder(user_id: int, text: str, when: str,
                          repeat: Optional[str] = None) -> dict:
    """Создать напоминание."""
    logger.info(f"[TOOL] create_reminder: user={user_id}, text={text}, when={when}, repeat={repeat}")
    reminder = {
        "id": _new_id("rem"),
        "text": text,
        "when": when,
        "repeat": repeat,
        "created_at": _now(),
        "status": "active",
    }
    _get_user_store("reminders", user_id).append(reminder)
    return {
        "status": "ok",
        "reminder_id": reminder["id"],
        "message": f"Напоминание «{text}» создано на {when}"
                   + (f" (повтор: {repeat})" if repeat else ""),
    }


async def list_reminders(user_id: int) -> dict:
    """Список напоминаний пользователя."""
    logger.info(f"[TOOL] list_reminders: user={user_id}")
    reminders = _get_user_store("reminders", user_id)
    return {
        "status": "ok",
        "count": len(reminders),
        "reminders": reminders,
    }


async def delete_reminder(user_id: int, reminder_id: str) -> dict:
    """Удалить напоминание по ID."""
    logger.info(f"[TOOL] delete_reminder: user={user_id}, id={reminder_id}")
    reminders = _get_user_store("reminders", user_id)
    for r in reminders:
        if r["id"] == reminder_id:
            reminders.remove(r)
            return {"status": "ok", "message": f"Напоминание {reminder_id} удалено"}
    return {"status": "error", "message": f"Напоминание {reminder_id} не найдено"}


async def set_reminder(user_id: int, text: str, when: str) -> dict:
    """Алиас create_reminder для агента питания."""
    return await create_reminder(user_id=user_id, text=text, when=when)


# ═══════════════════════════════════════════════════════════════
# КАТЕГОРИЯ 2: ЗАДАЧИ (task_manager, daily_planner)
# ═══════════════════════════════════════════════════════════════

async def create_task(user_id: int, title: str, deadline: Optional[str] = None,
                      priority: str = "medium", steps: Optional[list] = None) -> dict:
    """Создать задачу."""
    logger.info(f"[TOOL] create_task: user={user_id}, title={title}, priority={priority}")
    task = {
        "id": _new_id("task"),
        "title": title,
        "deadline": deadline,
        "priority": priority,
        "steps": steps or [],
        "status": "active",
        "created_at": _now(),
    }
    _get_user_store("tasks", user_id).append(task)
    return {
        "status": "ok",
        "task_id": task["id"],
        "message": f"Задача «{title}» добавлена. Приоритет: {priority}"
                   + (f", дедлайн: {deadline}" if deadline else ""),
    }


async def list_tasks(user_id: int, filter_status: str = "active") -> dict:
    """Список задач пользователя."""
    logger.info(f"[TOOL] list_tasks: user={user_id}, filter={filter_status}")
    tasks = _get_user_store("tasks", user_id)
    if filter_status:
        tasks = [t for t in tasks if t.get("status") == filter_status]
    # Сортировка: сначала high, потом medium, потом low
    priority_order = {"high": 0, "medium": 1, "low": 2}
    tasks_sorted = sorted(tasks, key=lambda t: priority_order.get(t.get("priority", "medium"), 1))
    return {
        "status": "ok",
        "count": len(tasks_sorted),
        "tasks": tasks_sorted,
    }


async def update_task(user_id: int, task_id: str, **kwargs) -> dict:
    """Обновить задачу."""
    logger.info(f"[TOOL] update_task: user={user_id}, id={task_id}, changes={kwargs}")
    tasks = _get_user_store("tasks", user_id)
    for t in tasks:
        if t["id"] == task_id:
            t.update({k: v for k, v in kwargs.items() if v is not None})
            return {"status": "ok", "message": f"Задача {task_id} обновлена", "task": t}
    return {"status": "error", "message": f"Задача {task_id} не найдена"}


async def delete_task(user_id: int, task_id: str) -> dict:
    """Удалить задачу."""
    logger.info(f"[TOOL] delete_task: user={user_id}, id={task_id}")
    tasks = _get_user_store("tasks", user_id)
    for t in tasks:
        if t["id"] == task_id:
            tasks.remove(t)
            return {"status": "ok", "message": f"Задача {task_id} удалена"}
    return {"status": "error", "message": f"Задача {task_id} не найдена"}


# ═══════════════════════════════════════════════════════════════
# КАТЕГОРИЯ 3: ПОДПИСКИ
# ═══════════════════════════════════════════════════════════════

async def add_subscription(user_id: int, name: str, amount: float,
                           period: str = "monthly",
                           next_charge_date: Optional[str] = None) -> dict:
    """Добавить подписку."""
    logger.info(f"[TOOL] add_subscription: user={user_id}, name={name}, amount={amount}")
    sub = {
        "id": _new_id("sub"),
        "name": name,
        "amount": amount,
        "currency": "RUB",
        "period": period,
        "next_charge_date": next_charge_date,
        "status": "active",
        "created_at": _now(),
    }
    _get_user_store("subscriptions", user_id).append(sub)
    return {"status": "ok", "subscription_id": sub["id"],
            "message": f"Подписка «{name}» добавлена: {amount} ₽ / {period}"}


async def list_subscriptions(user_id: int) -> dict:
    """Список подписок."""
    logger.info(f"[TOOL] list_subscriptions: user={user_id}")
    subs = _get_user_store("subscriptions", user_id)
    total = sum(s["amount"] for s in subs if s.get("status") == "active")
    return {
        "status": "ok",
        "count": len(subs),
        "total_monthly": total,
        "subscriptions": subs,
    }


async def cancel_subscription(user_id: int, subscription_id: str) -> dict:
    """Отменить подписку."""
    logger.info(f"[TOOL] cancel_subscription: user={user_id}, id={subscription_id}")
    subs = _get_user_store("subscriptions", user_id)
    for s in subs:
        if s["id"] == subscription_id:
            s["status"] = "cancelled"
            return {"status": "ok", "message": f"Подписка {subscription_id} отменена"}
    return {"status": "error", "message": f"Подписка {subscription_id} не найдена"}


async def get_subscription_summary(user_id: int) -> dict:
    """Сводка по подпискам."""
    logger.info(f"[TOOL] get_subscription_summary: user={user_id}")
    subs = _get_user_store("subscriptions", user_id)
    active = [s for s in subs if s.get("status") == "active"]
    total = sum(s["amount"] for s in active)
    return {
        "status": "ok",
        "active_count": len(active),
        "monthly_total": total,
        "yearly_total": total * 12,
        "message": f"У тебя {len(active)} активных подписок на {total} ₽/мес",
    }


# ═══════════════════════════════════════════════════════════════
# КАТЕГОРИЯ 4: УБОРКА
# ═══════════════════════════════════════════════════════════════

async def create_cleaning_task(user_id: int, title: str, frequency: str = "weekly",
                               next_date: Optional[str] = None) -> dict:
    """Создать задачу уборки."""
    logger.info(f"[TOOL] create_cleaning_task: user={user_id}, title={title}, freq={frequency}")
    task = {
        "id": _new_id("clean"),
        "title": title,
        "frequency": frequency,
        "next_date": next_date,
        "status": "active",
        "created_at": _now(),
    }
    _get_user_store("cleaning_tasks", user_id).append(task)
    return {"status": "ok", "task_id": task["id"],
            "message": f"Задача уборки «{title}» добавлена ({frequency})"}


async def list_cleaning_tasks(user_id: int) -> dict:
    """Список задач уборки."""
    logger.info(f"[TOOL] list_cleaning_tasks: user={user_id}")
    tasks = _get_user_store("cleaning_tasks", user_id)
    return {"status": "ok", "count": len(tasks), "tasks": tasks}


async def complete_task(user_id: int, task_id: str) -> dict:
    """Отметить задачу выполненной (уборка/семья)."""
    logger.info(f"[TOOL] complete_task: user={user_id}, id={task_id}")
    for store_name in ("cleaning_tasks", "family_tasks", "tasks"):
        store = _get_user_store(store_name, user_id)
        for t in store:
            if t["id"] == task_id:
                t["status"] = "completed"
                t["completed_at"] = _now()
                return {"status": "ok", "message": f"Задача {task_id} выполнена! 🎉"}
    return {"status": "error", "message": f"Задача {task_id} не найдена"}


# ═══════════════════════════════════════════════════════════════
# КАТЕГОРИЯ 5: СЕМЕЙНЫЕ ДЕЛА
# ═══════════════════════════════════════════════════════════════

async def create_family_task(user_id: int, title: str, assignee: str,
                             deadline: Optional[str] = None) -> dict:
    """Создать семейную задачу."""
    logger.info(f"[TOOL] create_family_task: user={user_id}, title={title}, assignee={assignee}")
    task = {
        "id": _new_id("fam"),
        "title": title,
        "assignee": assignee,
        "deadline": deadline,
        "status": "active",
        "created_at": _now(),
    }
    _get_user_store("family_tasks", user_id).append(task)
    return {"status": "ok", "task_id": task["id"],
            "message": f"Задача «{title}» назначена на {assignee}"}


async def list_family_tasks(user_id: int) -> dict:
    """Список семейных задач."""
    logger.info(f"[TOOL] list_family_tasks: user={user_id}")
    tasks = _get_user_store("family_tasks", user_id)
    # Группировка по исполнителям
    by_assignee: dict[str, list] = {}
    for t in tasks:
        by_assignee.setdefault(t["assignee"], []).append(t)
    return {"status": "ok", "count": len(tasks), "by_assignee": by_assignee}


async def assign_task(user_id: int, task_id: str, assignee: str) -> dict:
    """Переназначить задачу."""
    logger.info(f"[TOOL] assign_task: user={user_id}, id={task_id}, to={assignee}")
    tasks = _get_user_store("family_tasks", user_id)
    for t in tasks:
        if t["id"] == task_id:
            t["assignee"] = assignee
            return {"status": "ok", "message": f"Задача {task_id} переназначена на {assignee}"}
    return {"status": "error", "message": f"Задача {task_id} не найдена"}


# ═══════════════════════════════════════════════════════════════
# КАТЕГОРИЯ 6: ПОГОДА (weather, garden, daily_planner)
# ═══════════════════════════════════════════════════════════════

async def get_weather(location: str) -> dict:
    """Текущая погода. Заглушка. Позже — OpenWeather API."""
    logger.info(f"[TOOL] get_weather: location={location}")
    # Заглушка: возвращаем псевдослучайные, но правдоподобные данные
    return {
        "status": "ok",
        "location": location,
        "temperature": "+12",
        "feels_like": "+10",
        "condition": "облачно",
        "humidity": "72%",
        "wind": "3 м/с",
        "advice": "Возьми зонт, днём обещают дождь.",
        "updated_at": _now(),
    }


async def get_forecast(location: str, days: int = 3) -> dict:
    """Прогноз на несколько дней."""
    logger.info(f"[TOOL] get_forecast: location={location}, days={days}")
    today = datetime.now()
    forecast = []
    for i in range(min(days, 14)):
        d = today + timedelta(days=i)
        forecast.append({
            "date": d.strftime("%Y-%m-%d"),
            "weekday": d.strftime("%A"),
            "temp_day": f"+{10 + i}",
            "temp_night": f"+{2 + i}",
            "condition": ["ясно", "облачно", "дождь"][i % 3],
        })
    return {"status": "ok", "location": location, "forecast": forecast}


# ═══════════════════════════════════════════════════════════════
# КАТЕГОРИЯ 7: КАЛЕНДАРЬ И ДНИ РОЖДЕНИЯ
# ═══════════════════════════════════════════════════════════════

async def get_calendar(user_id: int, date: Optional[str] = None) -> dict:
    """События из календаря на дату."""
    logger.info(f"[TOOL] get_calendar: user={user_id}, date={date}")
    # Заглушка
    return {
        "status": "ok",
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "events": [
            {"time": "11:00", "title": "Встреча с командой", "duration": "1ч"},
            {"time": "15:30", "title": "Созвон с клиентом", "duration": "30м"},
        ],
    }


async def list_birthdays(user_id: int, days_ahead: int = 7) -> dict:
    """Дни рождения на ближайшие N дней."""
    logger.info(f"[TOOL] list_birthdays: user={user_id}, days_ahead={days_ahead}")
    birthdays = _get_user_store("birthdays", user_id)
    return {"status": "ok", "count": len(birthdays), "birthdays": birthdays}


async def add_birthday(user_id: int, name: str, date: str) -> dict:
    """Добавить день рождения."""
    logger.info(f"[TOOL] add_birthday: user={user_id}, name={name}, date={date}")
    bd = {"id": _new_id("bd"), "name": name, "date": date, "created_at": _now()}
    _get_user_store("birthdays", user_id).append(bd)
    return {"status": "ok", "birthday_id": bd["id"],
            "message": f"День рождения {name} ({date}) добавлен"}


# ═══════════════════════════════════════════════════════════════
# КАТЕГОРИЯ 8: ПОЧТА
# ═══════════════════════════════════════════════════════════════

async def get_emails(user_id: int, filter_unread: bool = True) -> dict:
    """Получить письма."""
    logger.info(f"[TOOL] get_emails: user={user_id}, unread={filter_unread}")
    # Заглушка
    return {
        "status": "ok",
        "total": 12,
        "unread": 5,
        "urgent": 2,
        "emails": [
            {"id": "em_001", "from": "boss@company.com", "subject": "Правки в отчёте",
             "priority": "high", "received": "10:23"},
            {"id": "em_002", "from": "client@corp.ru", "subject": "Договор на согласование",
             "priority": "high", "received": "09:15"},
        ],
    }


async def draft_reply(user_id: int, email_id: str, tone: str = "neutral") -> dict:
    """Создать черновик ответа на письмо."""
    logger.info(f"[TOOL] draft_reply: user={user_id}, email={email_id}, tone={tone}")
    draft = {
        "id": _new_id("draft"),
        "email_id": email_id,
        "tone": tone,
        "body": "Здравствуйте! Спасибо за письмо. Отвечу в ближайшее время.",
        "created_at": _now(),
    }
    _get_user_store("drafts", user_id).append(draft)
    return {"status": "ok", "draft_id": draft["id"],
            "message": "Черновик готов. Отправить?", "draft": draft}


async def send_email(user_id: int, to: str, subject: str, body: str) -> dict:
    """Отправить письмо."""
    logger.info(f"[TOOL] send_email: user={user_id}, to={to}")
    return {"status": "ok", "message": f"Письмо «{subject}» отправлено на {to}"}


async def mark_as_read(user_id: int, email_id: str) -> dict:
    """Отметить письмо как прочитанное."""
    logger.info(f"[TOOL] mark_as_read: user={user_id}, email={email_id}")
    return {"status": "ok", "message": f"Письмо {email_id} помечено прочитанным"}


# ═══════════════════════════════════════════════════════════════
# КАТЕГОРИЯ 9: ПИТАНИЕ
# ═══════════════════════════════════════════════════════════════

async def log_meal(user_id: int, description: str, meal_type: str = "lunch",
                   calories: Optional[int] = None) -> dict:
    """Записать приём пищи."""
    logger.info(f"[TOOL] log_meal: user={user_id}, desc={description}, type={meal_type}")
    meal = {
        "id": _new_id("meal"),
        "description": description,
        "meal_type": meal_type,
        "calories": calories,
        "logged_at": _now(),
    }
    _get_user_store("meals", user_id).append(meal)
    return {"status": "ok", "meal_id": meal["id"],
            "message": f"Записал: {description} ({meal_type})"}


async def log_water(user_id: int, amount_ml: int = 250) -> dict:
    """Записать стакан воды."""
    logger.info(f"[TOOL] log_water: user={user_id}, amount={amount_ml}ml")
    entry = {"id": _new_id("water"), "amount_ml": amount_ml, "logged_at": _now()}
    _get_user_store("water", user_id).append(entry)
    total = sum(w["amount_ml"] for w in _get_user_store("water", user_id))
    return {"status": "ok", "total_ml": total,
            "message": f"+{amount_ml}мл. Всего за день: {total}мл"}


async def get_nutrition_summary(user_id: int) -> dict:
    """Сводка по питанию и воде за день."""
    logger.info(f"[TOOL] get_nutrition_summary: user={user_id}")
    meals = _get_user_store("meals", user_id)
    water = _get_user_store("water", user_id)
    total_water = sum(w["amount_ml"] for w in water)
    total_cal = sum(m.get("calories") or 0 for m in meals)
    return {
        "status": "ok",
        "meals_count": len(meals),
        "total_calories": total_cal,
        "water_ml": total_water,
        "water_goal_ml": 2000,
        "message": f"Съедено: {len(meals)} приёмов, вода: {total_water}/2000 мл",
    }


# ═══════════════════════════════════════════════════════════════
# КАТЕГОРИЯ 10: ПСИХИЧЕСКОЕ ЗДОРОВЬЕ
# ═══════════════════════════════════════════════════════════════

async def log_mood(user_id: int, mood: int, note: Optional[str] = None) -> dict:
    """Записать настроение (1-10)."""
    logger.info(f"[TOOL] log_mood: user={user_id}, mood={mood}")
    entry = {"id": _new_id("mood"), "mood": mood, "note": note, "logged_at": _now()}
    _get_user_store("moods", user_id).append(entry)
    return {"status": "ok", "message": f"Записал настроение: {mood}/10"}


async def get_mood_history(user_id: int, days: int = 7) -> dict:
    """История настроения за N дней."""
    logger.info(f"[TOOL] get_mood_history: user={user_id}, days={days}")
    moods = _get_user_store("moods", user_id)
    avg = sum(m["mood"] for m in moods) / len(moods) if moods else 0
    return {"status": "ok", "entries": moods[-days:], "average": round(avg, 1)}


async def suggest_practice(user_id: int, state: str = "neutral") -> dict:
    """Предложить практику по состоянию."""
    logger.info(f"[TOOL] suggest_practice: user={user_id}, state={state}")
    practices = {
        "anxious": {"name": "Дыхание 4-7-8", "duration": "2 мин",
                    "steps": "Вдох 4 сек — задержка 7 сек — выдох 8 сек. Повтори 4 раза."},
        "low": {"name": "Дневник благодарности", "duration": "5 мин",
                "steps": "Запиши 3 вещи, за которые ты благодарен сегодня."},
        "neutral": {"name": "Заземление 5-4-3-2-1", "duration": "3 мин",
                    "steps": "5 вещей видишь, 4 слышишь, 3 трогаешь, 2 чувствуешь запах, 1 вкус."},
    }
    practice = practices.get(state, practices["neutral"])
    return {"status": "ok", "practice": practice}


# ═══════════════════════════════════════════════════════════════
# КАТЕГОРИЯ 11: ЮРИДИЧЕСКИЕ
# ═══════════════════════════════════════════════════════════════

async def search_legal_base(query: str, area: str = "general") -> dict:
    """Поиск в правовой базе."""
    logger.info(f"[TOOL] search_legal_base: query={query}, area={area}")
    return {
        "status": "ok",
        "query": query,
        "results": [
            {"title": "ГК РФ ст. 309", "snippet": "Обязательства должны исполняться надлежащим образом..."},
            {"title": "ГК РФ ст. 310", "snippet": "Односторонний отказ от исполнения обязательства..."},
        ],
        "disclaimer": "Это справочная информация, не юридическая консультация.",
    }


async def analyze_document(document_text: str, doc_type: str = "contract") -> dict:
    """Анализ юридического документа."""
    logger.info(f"[TOOL] analyze_document: type={doc_type}, len={len(document_text)}")
    return {
        "status": "ok",
        "doc_type": doc_type,
        "key_points": [
            "Срок действия: 12 месяцев",
            "Штраф за просрочку: 0,5% в день",
            "Автопродление при отсутствии возражений",
        ],
        "risks": [
            {"level": "high", "text": "Штраф 0,5%/день — выше рыночного (обычно 0,1%)"},
            {"level": "medium", "text": "Автопродление без уведомления"},
        ],
        "disclaimer": "Это шаблонный анализ. Проверьте с юристом.",
    }


async def set_legal_deadline(user_id: int, title: str, date: str,
                             description: Optional[str] = None) -> dict:
    """Установить юридический дедлайн."""
    logger.info(f"[TOOL] set_legal_deadline: user={user_id}, title={title}, date={date}")
    deadline = {
        "id": _new_id("legal"),
        "title": title,
        "date": date,
        "description": description,
        "created_at": _now(),
    }
    _get_user_store("reminders", user_id).append({
        "id": deadline["id"], "text": f"⚖️ {title}", "when": date, "status": "active"
    })
    return {"status": "ok", "deadline_id": deadline["id"],
            "message": f"Дедлайн «{title}» на {date} установлен и добавлен в напоминания"}


# ═══════════════════════════════════════════════════════════════
# КАТЕГОРИЯ 12: АНАЛИТИКА
# ═══════════════════════════════════════════════════════════════

async def query_data(source: str, query: str, filters: Optional[dict] = None) -> dict:
    """Запрос данных из источника."""
    logger.info(f"[TOOL] query_data: source={source}, query={query}")
    return {
        "status": "ok",
        "source": source,
        "rows": 150,
        "columns": ["date", "revenue", "orders", "conversion"],
        "sample": [
            {"date": "2026-09-28", "revenue": 125000, "orders": 47, "conversion": 0.042},
            {"date": "2026-09-29", "revenue": 98000, "orders": 35, "conversion": 0.031},
        ],
    }


async def build_report(data: dict, report_type: str = "summary") -> dict:
    """Построить отчёт."""
    logger.info(f"[TOOL] build_report: type={report_type}")
    return {
        "status": "ok",
        "report_type": report_type,
        "summary": "Продажи за неделю: 1 250 000 ₽ (+12%). Конверсия упала с 4,2% до 3,1%.",
        "insights": [
            "Драйвер роста — новый канал привлечения",
            "Проблема на этапе оплаты: падение конверсии",
        ],
    }


async def find_anomalies(data: dict, sensitivity: str = "medium") -> dict:
    """Найти аномалии в данных."""
    logger.info(f"[TOOL] find_anomalies: sensitivity={sensitivity}")
    return {
        "status": "ok",
        "anomalies": [
            {"date": "2026-09-29", "metric": "conversion", "value": 0.031,
             "expected": 0.042, "deviation": "-26%"},
        ],
    }


async def visualize(data: dict, chart_type: str = "line", title: str = "") -> dict:
    """Построить визуализацию."""
    logger.info(f"[TOOL] visualize: type={chart_type}, title={title}")
    return {
        "status": "ok",
        "chart_type": chart_type,
        "title": title,
        "image_url": "https://example.com/chart.png",  # заглушка
        "message": "График построен",
    }


# ═══════════════════════════════════════════════════════════════
# КАТЕГОРИЯ 13: ПЕРЕВОД
# ═══════════════════════════════════════════════════════════════

async def translate_text(text: str, target_lang: str,
                         source_lang: str = "auto", tone: str = "neutral") -> dict:
    """Перевести текст."""
    logger.info(f"[TOOL] translate_text: {source_lang}->{target_lang}, tone={tone}")
    return {
        "status": "ok",
        "source_lang": source_lang,
        "target_lang": target_lang,
        "translation": f"[Перевод на {target_lang}]: {text}",
        "note": "Заглушка. Подключите DeepL или Google Translate API.",
    }


async def lookup_dictionary(word: str, lang: str = "en") -> dict:
    """Найти слово в словаре."""
    logger.info(f"[TOOL] lookup_dictionary: word={word}, lang={lang}")
    return {
        "status": "ok",
        "word": word,
        "definitions": [f"Значение слова «{word}» (заглушка)"],
        "synonyms": [],
    }


async def explain_idiom(idiom: str, lang: str = "en") -> dict:
    """Объяснить идиому."""
    logger.info(f"[TOOL] explain_idiom: idiom={idiom}, lang={lang}")
    return {
        "status": "ok",
        "idiom": idiom,
        "meaning": "Значение идиомы (заглушка)",
        "equivalent": "Аналог в русском языке (заглушка)",
    }


# ═══════════════════════════════════════════════════════════════
# КАТЕГОРИЯ 14: КОПИРАЙТИНГ
# ═══════════════════════════════════════════════════════════════

async def check_style(text: str, style: str = "neutral") -> dict:
    """Проверить стиль текста."""
    logger.info(f"[TOOL] check_style: len={len(text)}, style={style}")
    return {
        "status": "ok",
        "readability": "8/10",
        "issues": [
            {"type": "cliche", "text": "канцелярит: «в целях осуществления»"},
        ],
        "suggestions": ["Заменить пассив на актив", "Сократить предложения до 15 слов"],
    }


async def generate_headlines(topic: str, count: int = 3,
                             style: str = "engaging") -> dict:
    """Сгенерировать заголовки."""
    logger.info(f"[TOOL] generate_headlines: topic={topic}, count={count}")
    return {
        "status": "ok",
        "headlines": [f"Вариант {i+1}: {topic}" for i in range(count)],
    }


async def save_draft(user_id: int, title: str, body: str) -> dict:
    """Сохранить черновик текста."""
    logger.info(f"[TOOL] save_draft: user={user_id}, title={title}")
    draft = {"id": _new_id("txt"), "title": title, "body": body, "created_at": _now()}
    _get_user_store("drafts", user_id).append(draft)
    return {"status": "ok", "draft_id": draft["id"], "message": f"Черновик «{title}» сохранён"}


# ═══════════════════════════════════════════════════════════════
# КАТЕГОРИЯ 15: САД
# ═══════════════════════════════════════════════════════════════

async def add_plant(user_id: int, name: str, species: Optional[str] = None,
                    watering_days: int = 3) -> dict:
    """Добавить растение."""
    logger.info(f"[TOOL] add_plant: user={user_id}, name={name}, species={species}")
    plant = {
        "id": _new_id("plant"),
        "name": name,
        "species": species,
        "watering_days": watering_days,
        "last_watered": None,
        "created_at": _now(),
    }
    _get_user_store("plants", user_id).append(plant)
    return {"status": "ok", "plant_id": plant["id"],
            "message": f"Растение «{name}» добавлено (полив каждые {watering_days} дн.)"}


async def list_plants(user_id: int) -> dict:
    """Список растений."""
    logger.info(f"[TOOL] list_plants: user={user_id}")
    plants = _get_user_store("plants", user_id)
    return {"status": "ok", "count": len(plants), "plants": plants}


async def watering_schedule(user_id: int) -> dict:
    """Расписание полива."""
    logger.info(f"[TOOL] watering_schedule: user={user_id}")
    plants = _get_user_store("plants", user_id)
    schedule = [
        {"plant": p["name"], "next_watering": "завтра" if i % 2 == 0 else "через 2 дня"}
        for i, p in enumerate(plants)
    ]
    return {"status": "ok", "schedule": schedule}


# ═══════════════════════════════════════════════════════════════
# РЕЕСТР ИНСТРУМЕНТОВ
# ═══════════════════════════════════════════════════════════════

TOOL_REGISTRY: dict[str, callable] = {
    # Напоминания
    "create_reminder": create_reminder,
    "list_reminders": list_reminders,
    "delete_reminder": delete_reminder,
    "set_reminder": set_reminder,
    # Задачи
    "create_task": create_task,
    "list_tasks": list_tasks,
    "update_task": update_task,
    "delete_task": delete_task,
    # Подписки
    "add_subscription": add_subscription,
    "list_subscriptions": list_subscriptions,
    "cancel_subscription": cancel_subscription,
    "get_subscription_summary": get_subscription_summary,
    # Уборка
    "create_cleaning_task": create_cleaning_task,
    "list_cleaning_tasks": list_cleaning_tasks,
    "complete_task": complete_task,
    # Семья
    "create_family_task": create_family_task,
    "list_family_tasks": list_family_tasks,
    "assign_task": assign_task,
    # Погода
    "get_weather": get_weather,
    "get_forecast": get_forecast,
    # Календарь
    "get_calendar": get_calendar,
    "list_birthdays": list_birthdays,
    "add_birthday": add_birthday,
    # Почта
    "get_emails": get_emails,
    "draft_reply": draft_reply,
    "send_email": send_email,
    "mark_as_read": mark_as_read,
    # Питание
    "log_meal": log_meal,
    "log_water": log_water,
    "get_nutrition_summary": get_nutrition_summary,
    # Психика
    "log_mood": log_mood,
    "get_mood_history": get_mood_history,
    "suggest_practice": suggest_practice,
    # Юрист
    "search_legal_base": search_legal_base,
    "analyze_document": analyze_document,
    "set_legal_deadline": set_legal_deadline,
    # Аналитик
    "query_data": query_data,
    "build_report": build_report,
    "find_anomalies": find_anomalies,
    "visualize": visualize,
    # Переводчик
    "translate_text": translate_text,
    "lookup_dictionary": lookup_dictionary,
    "explain_idiom": explain_idiom,
    # Копирайтер
    "check_style": check_style,
    "generate_headlines": generate_headlines,
    "save_draft": save_draft,
    # Сад
    "add_plant": add_plant,
    "list_plants": list_plants,
    "watering_schedule": watering_schedule,
}


# ═══════════════════════════════════════════════════════════════
# СХЕМЫ ДЛЯ OPENAI FUNCTION CALLING
# ═══════════════════════════════════════════════════════════════
# Формат: {"type": "function", "function": {...}}

TOOL_SCHEMAS: dict[str, dict] = {
    "create_reminder": {
        "type": "function",
        "function": {
            "name": "create_reminder",
            "description": "Создать напоминание на конкретное время",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Текст напоминания"},
                    "when": {"type": "string", "description": "Когда напомнить (ISO или естественный язык)"},
                    "repeat": {"type": "string", "description": "Повтор: daily, weekly, monthly"},
                },
                "required": ["text", "when"],
            },
        },
    },
    "list_reminders": {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "Показать все напоминания пользователя",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    "delete_reminder": {
        "type": "function",
        "function": {
            "name": "delete_reminder",
            "description": "Удалить напоминание по ID",
            "parameters": {
                "type": "object",
                "properties": {"reminder_id": {"type": "string"}},
                "required": ["reminder_id"],
            },
        },
    },
    "create_task": {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Создать задачу с дедлайном и приоритетом",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "deadline": {"type": "string"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                    "steps": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title"],
            },
        },
    },
    "list_tasks": {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "Показать задачи пользователя",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter_status": {"type": "string", "enum": ["active", "completed", "all"]},
                },
            },
        },
    },
    "update_task": {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Обновить задачу",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "title": {"type": "string"},
                    "deadline": {"type": "string"},
                    "priority": {"type": "string"},
                    "status": {"type": "string"},
                },
                "required": ["task_id"],
            },
        },
    },
    "delete_task": {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": "Удалить задачу",
            "parameters": {
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"],
            },
        },
    },
    "add_subscription": {
        "type": "function",
        "function": {
            "name": "add_subscription",
            "description": "Добавить подписку в трекер",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "amount": {"type": "number"},
                    "period": {"type": "string", "enum": ["monthly", "yearly", "weekly"]},
                    "next_charge_date": {"type": "string"},
                },
                "required": ["name", "amount"],
            },
        },
    },
    "list_subscriptions": {
        "type": "function",
        "function": {
            "name": "list_subscriptions",
            "description": "Показать все подписки",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    "cancel_subscription": {
        "type": "function",
        "function": {
            "name": "cancel_subscription",
            "description": "Отменить подписку",
            "parameters": {
                "type": "object",
                "properties": {"subscription_id": {"type": "string"}},
                "required": ["subscription_id"],
            },
        },
    },
    "get_subscription_summary": {
        "type": "function",
        "function": {
            "name": "get_subscription_summary",
            "description": "Сводка по подпискам и расходам",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    "create_cleaning_task": {
        "type": "function",
        "function": {
            "name": "create_cleaning_task",
            "description": "Создать задачу уборки",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "frequency": {"type": "string", "enum": ["daily", "weekly", "monthly", "seasonal"]},
                    "next_date": {"type": "string"},
                },
                "required": ["title"],
            },
        },
    },
    "list_cleaning_tasks": {
        "type": "function",
        "function": {
            "name": "list_cleaning_tasks",
            "description": "Список задач уборки",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    "complete_task": {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Отметить задачу выполненной",
            "parameters": {
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"],
            },
        },
    },
    "create_family_task": {
        "type": "function",
        "function": {
            "name": "create_family_task",
            "description": "Создать семейную задачу с ответственным",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "assignee": {"type": "string"},
                    "deadline": {"type": "string"},
                },
                "required": ["title", "assignee"],
            },
        },
    },
    "list_family_tasks": {
        "type": "function",
        "function": {
            "name": "list_family_tasks",
            "description": "Список семейных задач по исполнителям",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    "assign_task": {
        "type": "function",
        "function": {
            "name": "assign_task",
            "description": "Переназначить задачу",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "assignee": {"type": "string"},
                },
                "required": ["task_id", "assignee"],
            },
        },
    },
    "get_weather": {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Получить текущую погоду в указанном месте",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "Город или координаты"},
                },
                "required": ["location"],
            },
        },
    },
    "get_forecast": {
        "type": "function",
        "function": {
            "name": "get_forecast",
            "description": "Прогноз погоды на несколько дней",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"},
                    "days": {"type": "integer", "minimum": 1, "maximum": 14},
                },
                "required": ["location"],
            },
        },
    },
    "get_calendar": {
        "type": "function",
        "function": {
            "name": "get_calendar",
            "description": "События из календаря на дату",
            "parameters": {
                "type": "object",
                "properties": {"date": {"type": "string"}},
            },
        },
    },
    "list_birthdays": {
        "type": "function",
        "function": {
            "name": "list_birthdays",
            "description": "Дни рождения на ближайшие N дней",
            "parameters": {
                "type": "object",
                "properties": {"days_ahead": {"type": "integer"}},
            },
        },
    },
    "add_birthday": {
        "type": "function",
        "function": {
            "name": "add_birthday",
            "description": "Добавить день рождения",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["name", "date"],
            },
        },
    },
    "get_emails": {
        "type": "function",
        "function": {
            "name": "get_emails",
            "description": "Получить список писем",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter_unread": {"type": "boolean"},
                },
            },
        },
    },
    "draft_reply": {
        "type": "function",
        "function": {
            "name": "draft_reply",
            "description": "Создать черновик ответа на письмо",
            "parameters": {
                "type": "object",
                "properties": {
                    "email_id": {"type": "string"},
                    "tone": {"type": "string", "enum": ["neutral", "formal", "friendly"]},
                },
                "required": ["email_id"],
            },
        },
    },
    "send_email": {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Отправить письмо",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
    "mark_as_read": {
        "type": "function",
        "function": {
            "name": "mark_as_read",
            "description": "Отметить письмо прочитанным",
            "parameters": {
                "type": "object",
                "properties": {"email_id": {"type": "string"}},
                "required": ["email_id"],
            },
        },
    },
    "log_meal": {
        "type": "function",
        "function": {
            "name": "log_meal",
            "description": "Записать приём пищи",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "meal_type": {"type": "string", "enum": ["breakfast", "lunch", "dinner", "snack"]},
                    "calories": {"type": "integer"},
                },
                "required": ["description"],
            },
        },
    },
    "log_water": {
        "type": "function",
        "function": {
            "name": "log_water",
            "description": "Записать выпитую воду",
            "parameters": {
                "type": "object",
                "properties": {"amount_ml": {"type": "integer"}},
            },
        },
    },
    "get_nutrition_summary": {
        "type": "function",
        "function": {
            "name": "get_nutrition_summary",
            "description": "Сводка по питанию и воде за день",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    "set_reminder": {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": "Установить напоминание",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "when": {"type": "string"},
                },
                "required": ["text", "when"],
            },
        },
    },
    "log_mood": {
        "type": "function",
        "function": {
            "name": "log_mood",
            "description": "Записать настроение (1-10)",
            "parameters": {
                "type": "object",
                "properties": {
                    "mood": {"type": "integer", "minimum": 1, "maximum": 10},
                    "note": {"type": "string"},
                },
                "required": ["mood"],
            },
        },
    },
    "get_mood_history": {
        "type": "function",
        "function": {
            "name": "get_mood_history",
            "description": "История настроения за N дней",
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer"}},
            },
        },
    },
    "suggest_practice": {
        "type": "function",
        "function": {
            "name": "suggest_practice",
            "description": "Предложить практику по состоянию",
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {"type": "string", "enum": ["anxious", "low", "neutral"]},
                },
            },
        },
    },
    "search_legal_base": {
        "type": "function",
        "function": {
            "name": "search_legal_base",
            "description": "Поиск в правовой базе",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "area": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
    "analyze_document": {
        "type": "function",
        "function": {
            "name": "analyze_document",
            "description": "Анализ юридического документа",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_text": {"type": "string"},
                    "doc_type": {"type": "string", "enum": ["contract", "claim", "letter"]},
                },
                "required": ["document_text"],
            },
        },
    },
    "set_legal_deadline": {
        "type": "function",
        "function": {
            "name": "set_legal_deadline",
            "description": "Установить юридический дедлайн",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "date": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["title", "date"],
            },
        },
    },
    "query_data": {
        "type": "function",
        "function": {
            "name": "query_data",
            "description": "Запрос данных из источника",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "query": {"type": "string"},
                    "filters": {"type": "object"},
                },
                "required": ["source", "query"],
            },
        },
    },
    "build_report": {
        "type": "function",
        "function": {
            "name": "build_report",
            "description": "Построить отчёт по данным",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {"type": "object"},
                    "report_type": {"type": "string", "enum": ["summary", "detailed", "executive"]},
                },
                "required": ["data"],
            },
        },
    },
    "find_anomalies": {
        "type": "function",
        "function": {
            "name": "find_anomalies",
            "description": "Найти аномалии в данных",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {"type": "object"},
                    "sensitivity": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["data"],
            },
        },
    },
    "visualize": {
        "type": "function",
        "function": {
            "name": "visualize",
            "description": "Построить график",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {"type": "object"},
                    "chart_type": {"type": "string", "enum": ["line", "bar", "pie", "scatter"]},
                    "title": {"type": "string"},
                },
                "required": ["data"],
            },
        },
    },
    "translate_text": {
        "type": "function",
        "function": {
            "name": "translate_text",
            "description": "Перевести текст",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "target_lang": {"type": "string"},
                    "source_lang": {"type": "string"},
                    "tone": {"type": "string", "enum": ["neutral", "formal", "friendly"]},
                },
                "required": ["text", "target_lang"],
            },
        },
    },
    "lookup_dictionary": {
        "type": "function",
        "function": {
            "name": "lookup_dictionary",
            "description": "Найти слово в словаре",
            "parameters": {
                "type": "object",
                "properties": {
                    "word": {"type": "string"},
                    "lang": {"type": "string"},
                },
                "required": ["word"],
            },
        },
    },
    "explain_idiom": {
        "type": "function",
        "function": {
            "name": "explain_idiom",
            "description": "Объяснить идиому",
            "parameters": {
                "type": "object",
                "properties": {
                    "idiom": {"type": "string"},
                    "lang": {"type": "string"},
                },
                "required": ["idiom"],
            },
        },
    },
    "check_style": {
        "type": "function",
        "function": {
            "name": "check_style",
            "description": "Проверить стиль текста",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "style": {"type": "string"},
                },
                "required": ["text"],
            },
        },
    },
    "generate_headlines": {
        "type": "function",
        "function": {
            "name": "generate_headlines",
            "description": "Сгенерировать варианты заголовков",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "count": {"type": "integer"},
                    "style": {"type": "string"},
                },
                "required": ["topic"],
            },
        },
    },
    "save_draft": {
        "type": "function",
        "function": {
            "name": "save_draft",
            "description": "Сохранить черновик текста",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["title", "body"],
            },
        },
    },
    "add_plant": {
        "type": "function",
        "function": {
            "name": "add_plant",
            "description": "Добавить растение в дневник",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "species": {"type": "string"},
                    "watering_days": {"type": "integer"},
                },
                "required": ["name"],
            },
        },
    },
    "list_plants": {
        "type": "function",
        "function": {
            "name": "list_plants",
            "description": "Список растений пользователя",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    "watering_schedule": {
        "type": "function",
        "function": {
            "name": "watering_schedule",
            "description": "Расписание полива",
            "parameters": {"type": "object", "properties": {}},
        },
    },
}


def get_tools_for_agent(tool_names: list[str]) -> list[dict]:
    """Получить список схем инструментов для конкретного агента."""
    return [TOOL_SCHEMAS[name] for name in tool_names if name in TOOL_SCHEMAS]


# ═══════════════════════════════════════════════════════════════
# ЕДИНАЯ ТОЧКА ВЫПОЛНЕНИЯ
# ═══════════════════════════════════════════════════════════════

async def execute_tool(tool_name: str, user_id: int, **kwargs) -> dict:
    """
    Выполнить инструмент по имени.

    Автоматически подставляет user_id, если инструмент его принимает.
    """
    tool = TOOL_REGISTRY.get(tool_name)
    if not tool:
        logger.warning(f"[TOOL] Неизвестный инструмент: {tool_name}")
        return {"status": "error", "message": f"Инструмент '{tool_name}' не найден"}

    # Добавляем user_id, если функция его принимает
    import inspect
    sig = inspect.signature(tool)
    if "user_id" in sig.parameters:
        kwargs["user_id"] = user_id

    try:
        result = await tool(**kwargs)
        logger.info(f"[TOOL] {tool_name} → {result.get('status', 'unknown')}")
        return result
    except TypeError as e:
        logger.error(f"[TOOL] {tool_name} — неверные аргументы: {e}")
        return {"status": "error", "message": f"Ошибка аргументов: {e}"}
    except Exception as e:
        logger.error(f"[TOOL] {tool_name} — ошибка: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


# ═══════════════════════════════════════════════════════════════
# САМОПРОВЕРКА
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import asyncio

    async def _test():
        print(f"✅ Загружено инструментов: {len(TOOL_REGISTRY)}")
        print(f"✅ Схем для function calling: {len(TOOL_SCHEMAS)}\n")

        # Проверяем, что все tools из agents.py есть в реестре
        from agents import AGENTS
        missing = []
        for agent in AGENTS.values():
            for t in agent.tools:
                if t not in TOOL_REGISTRY:
                    missing.append(f"{agent.id}.{t}")

        if missing:
            print("❌ Отсутствуют инструменты:")
            for m in missing:
                print(f"   - {m}")
        else:
            print("✅ Все инструменты из agents.py присутствуют в реестре")

        # Демо-вызовы
        print("\n── Демо ──")
        r = await execute_tool("create_reminder", user_id=1,
                               text="Позвонить маме", when="завтра 10:00")
        print(f"create_reminder → {r['message']}")

        r = await execute_tool("list_reminders", user_id=1)
        print(f"list_reminders → {r['count']} напоминаний")

        r = await execute_tool("get_weather", user_id=1, location="Москва")
        print(f"get_weather → {r['temperature']}, {r['condition']}")

        r = await execute_tool("log_water", user_id=1, amount_ml=250)
        print(f"log_water → {r['message']}")

    asyncio.run(_test())
