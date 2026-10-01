"""
bot.py — Точка входа телеграм-бота с интеграцией AI-агентов.

Что внутри:
- Инициализация Bot и Dispatcher (aiogram 3.x)
- Подключение agents_router (все 16 агентов)
- Запуск планировщика напоминаний (scheduler.py)
- Базовые хендлеры: /start, /help, /agents, /exit, /reset
- Главное меню с кнопками
- Healthcheck LLM при старте
- Graceful shutdown

Запуск:
    python bot.py
"""

import asyncio
import logging
import os
import sys

# ─── Загружаем .env ─────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─── aiogram ────────────────────────────────────────────────────
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
)

# ─── Роутер агентов ─────────────────────────────────────────────
from agent_handlers import agents_router
from agent_router import healthcheck, is_llm_configured, get_llm_info


# ─── БД и планировщик ───────────────────────────────────────────
from database import init_db
from scheduler import reminder_worker


# ═══════════════════════════════════════════════════════════════
# НАСТРОЙКИ
# ═══════════════════════════════════════════════════════════════

class _FallbackSettings:
    """Fallback, если config.py отсутствует."""
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: str = os.getenv("ADMIN_IDS", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./bot.db")

    @property
    def admin_ids_list(self) -> list[int]:
        if not self.ADMIN_IDS:
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip().isdigit()]


try:
    from config import settings  # type: ignore
except ImportError:
    settings = _FallbackSettings()


# ═══════════════════════════════════════════════════════════════
# ЛОГИРОВАНИЕ
# ═══════════════════════════════════════════════════════════════

def _setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)-20s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


_setup_logging()
logger = logging.getLogger("bot")


def _validate_settings() -> None:
    if not getattr(settings, "BOT_TOKEN", ""):
        logger.error("❌ BOT_TOKEN не задан! Добавь его в переменные окружения.")
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════
# BOT И DISPATCHER
# ═══════════════════════════════════════════════════════════════

try:
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
except Exception:
    bot = Bot(token=settings.BOT_TOKEN, parse_mode=ParseMode.MARKDOWN)

storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# ═══════════════════════════════════════════════════════════════
# ГЛАВНОЕ МЕНЮ
# ═══════════════════════════════════════════════════════════════

def _build_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 AI-агенты", callback_data="agents:menu")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help")],
    ])


try:
    from keyboards import main_menu as _external_main_menu  # type: ignore
    def get_main_menu() -> InlineKeyboardMarkup:
        return _external_main_menu()
except (ImportError, AttributeError):
    def get_main_menu() -> InlineKeyboardMarkup:
        return _build_main_menu()


# ═══════════════════════════════════════════════════════════════
# БАЗОВЫЕ ХЕНДЛЕРЫ
# ═══════════════════════════════════════════════════════════════

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_name = message.from_user.first_name or "друг"

    llm_note = ""
    if not is_llm_configured():
        llm_note = "\n\n⚠️ _AI не настроен — агенты работают в демо-режиме._"

    text = (
        f"👋 Привет, *{user_name}*!\n\n"
        f"Я — бот с *10 AI-агентами*. Каждый специализируется "
        f"на своей задаче:\n\n"
        f"🗂️ Продуктивность — напоминания, дела, план, подписки, уборка\n"
        f"📡 Информация — погода, дни рождения\n"
        f"💼 Работа — аналитик, копирайтер\n"
        f"🏡 Дом — цветы и полив\n\n"
        f"Нажми *«🤖 AI-агенты»* или отправь /agents, чтобы начать."
        f"{llm_note}"
    )
    await message.answer(text, reply_markup=get_main_menu())


@dp.message(Command("help"))
async def cmd_help(message: Message):
        text = (
        "📖 *Справка*\n\n"
        "*Основные команды:*\n"
        "• /start — главное меню\n"
        "• /agents — список AI-агентов\n"
        "• /help — эта справка\n"
        "• /exit — выйти из чата с агентом\n"
        "• /reset — сбросить состояние\n\n"
        "*Как работать с агентами:*\n"
        "1. Отправь /agents\n"
        "2. Выбери агента из списка\n"
        "3. Нажми на кнопку или напиши свой вопрос\n"
        "4. Кнопка «🔙 Назад» возвращает к списку агентов"
    )
    await message.answer(text)


@dp.message(Command("status"))
async def cmd_status(message: Message):
    admin_ids = getattr(settings, "admin_ids_list", [])
    user_id = message.from_user.id if message.from_user else 0

    if admin_ids and user_id not in admin_ids:
        await message.answer("🔒 Команда только для админов.")
        return

    info = get_llm_info()
    hc = await healthcheck()

    text = (
        f"⚙️ *Статус системы*\n\n"
        f"*LLM:*\n"
        f"• Провайдер: `{info['provider']}`\n"
        f"• Модель: `{info['model']}`\n"
        f"• Статус: `{hc['status']}`\n\n"
    )

    if hc["status"] == "ok":
        text += f"• Ответ модели: `{hc.get('response_preview', '')[:40]}`\n"
    elif hc["status"] == "error":
        text += f"• Ошибка: `{hc.get('error', 'unknown')[:80]}`\n"
    elif hc["status"] == "disabled":
        text += "• _API-ключ не настроен_\n"

    from agents import AGENTS
    total_agents = len(AGENTS)
    total_tools = sum(len(a.tools) for a in AGENTS.values())
    text += (
        f"\n*Агенты:*\n"
        f"• Всего: {total_agents}\n"
        f"• Инструментов: {total_tools}\n"
    )

    await message.answer(text)




# ═══════════════════════════════════════════════════════════════
# FALLBACK-ХЕНДЛЕР
# ═══════════════════════════════════════════════════════════════

@dp.message(StateFilter(None), F.text & ~F.text.startswith("/"))
async def handle_unknown(message: Message, state: FSMContext):
    """Fallback: только когда нет активного состояния."""
    await message.answer(
        "🤔 Не понял команду.\n\n"
        "Отправь /agents, чтобы выбрать AI-агента, "
        "или /help для справки."
    )


# ═══════════════════════════════════════════════════════════════
# ПОДКЛЮЧАЕМ РОУТЕР АГЕНТОВ
# ═══════════════════════════════════════════════════════════════

dp.include_router(agents_router)


# ═══════════════════════════════════════════════════════════════
# УСТАНОВКА КОМАНД
# ═══════════════════════════════════════════════════════════════

async def _set_bot_commands() -> None:
    commands = [
        BotCommand(command="start", description="🚀 Запустить бота"),
        BotCommand(command="agents", description="🤖 AI-агенты"),
        BotCommand(command="help", description="❓ Помощь"),
        BotCommand(command="status", description="⚙️ Статус (для админов)"),
        BotCommand(command="exit", description="🚪 Выйти из чата"),
        BotCommand(command="reset", description="♻️ Сбросить состояние"),
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info(f"✅ Установлено команд: {len(commands)}")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось установить команды: {e}")


# ═══════════════════════════════════════════════════════════════
# ЗАПУСК
# ═══════════════════════════════════════════════════════════════

async def main() -> None:
    logger.info("═" * 55)
    logger.info("  🤖 Telegram Bot with AI Agents")
    logger.info("═" * 55)

    # 1. Проверяем настройки
    _validate_settings()

    # 2. Инициализируем БД
    try:
        await init_db()
        logger.info("✅ БД инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")

    # 3. Healthcheck LLM
    info = get_llm_info()
    logger.info(
        f"LLM: provider={info['provider']}, model={info['model']}, "
        f"configured={'да' if info['configured'] else 'НЕТ (демо-режим)'}"
    )

    if info["configured"]:
        try:
            hc = await healthcheck()
            if hc["status"] == "ok":
                logger.info("✅ LLM отвечает")
            else:
                logger.warning(f"⚠️ LLM: {hc.get('error', hc['status'])}")
        except Exception as e:
            logger.warning(f"⚠️ Healthcheck упал: {e}")
    else:
        logger.warning(
            "⚠️ OPENAI_API_KEY или OPENROUTER_API_KEY не заданы — "
            "агенты работают в демо-режиме"
        )

    # 4. Устанавливаем команды
    await _set_bot_commands()

    # 5. Удаляем вебхук
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logger.debug(f"delete_webhook: {e}")

    # 6. Запускаем планировщик напоминаний
    scheduler_task = asyncio.create_task(reminder_worker(bot))
    logger.info("⏰ Планировщик напоминаний запущен")

    # 7. Запускаем polling
    logger.info("🚀 Бот запущен. Ctrl+C — остановка.\n")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        scheduler_task.cancel()
        await bot.session.close()
        logger.info("👋 Бот остановлен")


def run() -> None:
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Получен сигнал остановки")
    except Exception as e:
        logger.exception(f"❌ Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run()
