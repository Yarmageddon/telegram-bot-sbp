import asyncio
import logging
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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

from agent_handlers import agents_router
from agent_router import healthcheck, is_llm_configured, get_llm_info
from database import init_db
from scheduler import reminder_worker


class _FallbackSettings:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS = os.getenv("ADMIN_IDS", "")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bot.db")

    @property
    def admin_ids_list(self):
        if not self.ADMIN_IDS:
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip().isdigit()]


try:
    from config import settings
except ImportError:
    settings = _FallbackSettings()


def _setup_logging():
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


def _validate_settings():
    if not getattr(settings, "BOT_TOKEN", ""):
        logger.error("BOT_TOKEN not set")
        sys.exit(1)


try:
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
except Exception:
    bot = Bot(token=settings.BOT_TOKEN, parse_mode=ParseMode.MARKDOWN)

storage = MemoryStorage()
dp = Dispatcher(storage=storage)


def _build_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="AI-агенты", callback_data="agents:menu")],
        [InlineKeyboardButton(text="Помощь", callback_data="help")],
    ])


try:
    from keyboards import main_menu as _external_main_menu
    def get_main_menu():
        return _external_main_menu()
except (ImportError, AttributeError):
    def get_main_menu():
        return _build_main_menu()


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_name = message.from_user.first_name or "друг"
    llm_note = ""
    if not is_llm_configured():
        llm_note = "\n\nAI не настроен — агенты в демо-режиме."

    text = (
        f"Привет, {user_name}!\n\n"
        f"Я бот с 10 AI-агентами:\n\n"
        f"Продуктивность: напоминания, дела, план, подписки, уборка\n"
        f"Информация: погода, дни рождения\n"
        f"Работа: аналитик, копирайтер\n"
        f"Дом: цветы и полив\n\n"
        f"Нажми AI-агенты или отправь /agents."
        f"{llm_note}"
    )
    await message.answer(text, reply_markup=get_main_menu())


@dp.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "Справка\n\n"
        "Команды:\n"
        "/start — главное меню\n"
        "/agents — список агентов\n"
        "/help — справка\n"
        "/exit — выйти из чата\n"
        "/reset — сбросить состояние\n\n"
        "Как работать:\n"
        "1. Отправь /agents\n"
        "2. Выбери агента\n"
        "3. Нажми кнопку или напиши вопрос\n"
        "4. Кнопка Назад возвращает к списку"
    )
    await message.answer(text)


@dp.message(Command("status"))
async def cmd_status(message: Message):
    admin_ids = getattr(settings, "admin_ids_list", [])
    user_id = message.from_user.id if message.from_user else 0
    if admin_ids and user_id not in admin_ids:
        await message.answer("Команда только для админов.")
        return

    info = get_llm_info()
    hc = await healthcheck()

    text = f"Статус системы\n\nLLM:\nПровайдер: {info['provider']}\nМодель: {info['model']}\nСтатус: {hc['status']}\n"

    if hc["status"] == "ok":
        text += f"Ответ: {hc.get('response_preview', '')[:40]}\n"
    elif hc["status"] == "error":
        text += f"Ошибка: {hc.get('error', 'unknown')[:80]}\n"
    elif hc["status"] == "disabled":
        text += "Ключ не настроен\n"

    from agents import AGENTS
    total_agents = len(AGENTS)
    total_tools = sum(len(a.tools) for a in AGENTS.values())
    text += f"\nАгенты: {total_agents}\nИнструментов: {total_tools}\n"

    await message.answer(text)


@dp.message(StateFilter(None), F.text & ~F.text.startswith("/"))
async def handle_unknown(message: Message, state: FSMContext):
    await message.answer(
        "Не понял команду.\n\n"
        "Отправь /agents для выбора агента или /help."
    )


dp.include_router(agents_router)


async def _set_bot_commands():
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="agents", description="AI-агенты"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="status", description="Статус"),
        BotCommand(command="exit", description="Выйти"),
        BotCommand(command="reset", description="Сброс"),
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info(f"Commands set: {len(commands)}")
    except Exception as e:
        logger.warning(f"Commands error: {e}")


async def main():
    logger.info("=" * 55)
    logger.info("Telegram Bot with AI Agents")
    logger.info("=" * 55)

    _validate_settings()

    try:
        await init_db()
        logger.info("DB initialized")
    except Exception as e:
        logger.error(f"DB error: {e}")

    info = get_llm_info()
    logger.info(
        f"LLM: provider={info['provider']}, model={info['model']}, "
        f"configured={'yes' if info['configured'] else 'no'}"
    )

    if info["configured"]:
        try:
            hc = await healthcheck()
            if hc["status"] == "ok":
                logger.info("LLM OK")
            else:
                logger.warning(f"LLM: {hc.get('error', hc['status'])}")
        except Exception as e:
            logger.warning(f"Healthcheck failed: {e}")
    else:
        logger.warning("LLM key not set — demo mode")

    await _set_bot_commands()

    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logger.debug(f"delete_webhook: {e}")

    scheduler_task = asyncio.create_task(reminder_worker(bot))
    logger.info("Scheduler started")

    logger.info("Bot started\n")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        scheduler_task.cancel()
        await bot.session.close()
        logger.info("Bot stopped")


def run():
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopped")
    except Exception as e:
        logger.exception(f"Critical: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run()
