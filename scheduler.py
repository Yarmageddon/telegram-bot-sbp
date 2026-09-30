"""
scheduler.py — фоновый воркер для отложенных напоминаний.

Запускается из bot.py через asyncio.create_task(reminder_worker(bot)).

Логика:
1. Раз в 30 сек ищет напоминания со status='pending' и when <= now.
2. Отправляет пользователю сообщение через bot.send_message().
3. Помечает status='sent'.
4. Если repeat — создаёт следующее напоминание.
"""

import asyncio
import logging
from datetime import timedelta

from aiogram import Bot

from database import SessionLocal
from models import Reminder, utc_now

logger = logging.getLogger(__name__)

# Как часто проверять напоминания (в секундах)
CHECK_INTERVAL = 30


async def reminder_worker(bot: Bot) -> None:
    """Бесконечный цикл обработки напоминаний."""
    logger.info("⏰ Планировщик напоминаний запущен")

    # Небольшая пауза при старте, чтобы БД успела инициализироваться
    await asyncio.sleep(5)

    while True:
        try:
            await _process_due_reminders(bot)
        except Exception as e:
            logger.exception(f"[SCHEDULER] Ошибка: {e}")

        await asyncio.sleep(CHECK_INTERVAL)


async def _process_due_reminders(bot: Bot) -> None:
    """Обработать все напоминания, срок которых пришёл."""
    with SessionLocal() as db:
        now = utc_now()

        due = (
            db.query(Reminder)
            .filter(Reminder.status == "pending", Reminder.when <= now)
            .order_by(Reminder.when)
            .limit(50)  # защита от лавины
            .all()
        )

        if not due:
            return

        logger.info(f"[SCHEDULER] Обрабатываю {len(due)} напоминаний")

        for reminder in due:
            try:
                await bot.send_message(
                    chat_id=reminder.user_id,
                    text=f"🔔 *Напоминание*\n\n{reminder.text}",
                    parse_mode="Markdown",
                )
                reminder.status = "sent"
                reminder.sent_at = now
                logger.info(
                    f"[SCHEDULER] ✅ Отправлено user={reminder.user_id}: {reminder.text[:60]}"
                )
            except Exception as e:
                # Если пользователь заблокировал бота — просто помечаем
                logger.error(f"[SCHEDULER] Не удалось отправить {reminder.id}: {e}")
                reminder.status = "failed"

            # Повторяющиеся напоминания — создаём следующее
            if reminder.repeat and reminder.status == "sent":
                delta = _repeat_delta(reminder.repeat)
                if delta:
                    next_reminder = Reminder(
                        user_id=reminder.user_id,
                        text=reminder.text,
                        when=reminder.when + delta,
                        repeat=reminder.repeat,
                        related_type=reminder.related_type,
                        related_id=reminder.related_id,
                    )
                    db.add(next_reminder)

        db.commit()


def _repeat_delta(repeat: str):
    """Преобразовать строку repeat в timedelta."""
    return {
        "daily": timedelta(days=1),
        "weekly": timedelta(weeks=1),
        "monthly": timedelta(days=30),
    }.get(repeat)
