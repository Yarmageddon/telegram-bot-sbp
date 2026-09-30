"""
bot.py — Точка входа телеграм-бота с интеграцией AI-агентов.

Что внутри:
- Инициализация Bot и Dispatcher (aiogram 3.x)
- Подключение agents_router (все 16 агентов)
- Базовые хендлеры: /start, /help, /agents, /exit, /reset
- Главное меню с кнопками
- Healthcheck LLM при старте
- Graceful shutdown

Запуск:
    python bot.py

Зависимости:
    aiogram>=3.4.1
    httpx>=0.27.0
    python-dotenv>=1.0.0
    pydantic-settings>=2.0.0   (если используете config.Settings)
    sqlalchemy>=2.0.0          (опционально, для БД)
"""

import asyncio
import logging
import os
import sys
from typing import Optional

# ─── Загружаем .env (если есть python-dotenv) ───────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─── aiogram ────────────────────────────────────────────────────
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
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
from agent_keyboards import agents_main_menu


# ═══════════════════════════════════════════════════════════════
# НАСТРОЙКИ
# ═══════════════════════════════════════════════════════════════
# Пытаемся взять настройки из config.py. Если его нет — берём из env.

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
    logging.getLogger(__name__).debug("✅ Настройки загружены из config.py")
except ImportError:
    settings = _FallbackSettings()
    logging.getLogger(__name__).debug("⚠️ config.py не найден — используем env")


# ═══════════════════════════════════════════════════════════════
# ЛОГИРОВАНИЕ
# ═══════════════════════════════════════════════════════════════

def _setup_logging() -> None:
    """Настройка логирования."""
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)-20s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    # Приглушаем болтливые логи aiogram
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


_setup_logging()
logger = logging.getLogger("bot")


# ═══════════════════════════════════════════════════════════════
# ПРОВЕРКА КОНФИГУРАЦИИ
# ═══════════════════════════════════════════════════════════════

def _validate_settings() -> None:
    """Проверить, что все критичные настройки заданы."""
    if not getattr(settings, "BOT_TOKEN", ""):
        logger.error(
            "❌ BOT_TOKEN не задан!\n"
            "   1. Создай файл .env в корне проекта\n"
            "   2. Добавь строку: BOT_TOKEN=123456:ABC-DEF...\n"
            "   3. Получить токен: https://t.me/BotFather"
        )
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════
# ИНИЦИАЛИЗАЦИЯ БД (опционально)
# ═══════════════════════════════════════════════════════════════

async def _init_database() -> None:
    """
    Инициализация БД, если есть модуль database.py.
    Если нет — пропускаем, бот работает без БД.
    """
    try:
        from database import init_db  # type: ignore
        await init_db()
        logger.info("✅ БД инициализирована")
    except ImportError:
        logger.info("ℹ️ database.py не найден — БД не инициализируется")
    except Exception as e:
        logger.warning(f"⚠️ БД не инициализирована: {e}")


# ═══════════════════════════════════════════════════════════════
# BOT И DISPATCHER
# ═══════════════════════════════════════════════════════════════

# DefaultBotProperties — новый способ в aiogram 3.7+
try:
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
except Exception:
    # Fallback для старых версий aiogram 3.4.x
    bot = Bot(token=settings.BOT_TOKEN, parse_mode=ParseMode.MARKDOWN)

# Хранилище FSM в памяти (при перезапуске состояние сбрасывается)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# ═══════════════════════════════════════════════════════════════
# ГЛАВНОЕ МЕНЮ (fallback, если нет keyboards.py)
# ═══════════════════════════════════════════════════════════════

def _build_main_menu() -> InlineKeyboardMarkup:
    """Главное меню бота. Если есть keyboards.main_menu — используется оно."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🤖 AI-агенты", callback_data="agents:menu"),
        ],
        [
            InlineKeyboardButton(text="❓ Помощь", callback_data="help"),
        ],
    ])


# Пытаемся взять main_menu из keyboards.py
try:
    from keyboards import main_menu as _external_main_menu  # type: ignore
    def get_main_menu() -> InlineKeyboardMarkup:
        return _external_main_menu()
    logger.debug("✅ main_menu загружен из keyboards.py")
except (ImportError, AttributeError):
    def get_main_menu() -> InlineKeyboardMarkup:
        return _build_main_menu()
    logger.debug("ℹ️ keyboards.py не найден — используем встроенное меню")


# ═══════════════════════════════════════════════════════════════
# БАЗОВЫЕ ХЕНДЛЕРЫ
# ═══════════════════════════════════════════════════════════════

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Команда /start — приветствие и главное меню."""
    await state.clear()

    user_name = message.from_user.first_name or "друг"
    llm_note = ""
    if not is_llm_configured():
        llm_note = "\n\n⚠️ _AI не настроен — агенты работают в демо-режиме._"

    text = (
        f"👋 Привет, *{user_name}*!\n\n"
        f"Я — бот с *16 AI-агентами* на борту. Каждый специализируется "
        f"на своей задаче:\n\n"
        f"🗂️ Продуктивность — напоминания, задачи, подписки\n"
        f"📡 Информация — погода, календарь, почта\n"
        f"💚 Здоровье — питание, настроение\n"
        f"💼 Работа — юрист, аналитик, переводчик, копирайтер\n"
        f"🏡 Дом — сад и растения\n\n"
        f"Нажми *«🤖 AI-агенты»* или отправь /agents, чтобы начать."
        f"{llm_note}"
    )

    await message.answer(text, reply_markup=get_main_menu())


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Команда /help — справка."""
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
        "2. Выбери категорию или конкретного агента\n"
        "3. Нажми на готовый вопрос или напиши свой\n"
        "4. Веди диалог — агент помнит контекст последних 20 сообщений\n\n"
        "*Что умеют агенты:*\n"
        "• ⏰ Ставить напоминания\n"
        "• 📋 Управлять задачами\n"
        "• 💳 Следить за подписками\n"
        "• 🌤️ Рассказывать о погоде\n"
        "• 🎂 Напоминать о днях рождения\n"
        "• 📧 Разбирать почту\n"
        "• 🥗 Считать питание и воду\n"
        "• 🧘 Поддерживать настроение\n"
        "• ⚖️ Анализировать документы\n"
        "• 📊 Строить отчёты\n"
        "• 🌍 Переводить тексты\n"
        "• ✍️ Писать копирайт\n"
        "• 🌱 Ухаживать за растениями"
    )
    await message.answer(text)


@dp.message(Command("status"))
async def cmd_status(message: Message):
    """Команда /status — статус системы (для админов)."""
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

    # Статистика по агентам
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
# CALLBACK: help и agents:menu
# ═══════════════════════════════════════════════════════════════

@dp.callback_query(F.data == "help")
async def callback_help(callback: CallbackQuery):
    """Кнопка «Помощь»."""
    # Переиспользуем текст из /help
    await callback.message.answer(
        "📖 Отправь /help, чтобы увидеть полную справку."
    )
    await callback.answer()


    await callback.message.edit_text(
        f"🤖 *Агенты на связи!*\n\n"
        f"Доступно агентов: *{total}*\n"
        f"Выбери нужного:",
        reply_markup=agents_main_menu(),
        parse_mode="Markdown",
    )


@dp.callback_query(F.data == "back:main")
async def callback_back_main(callback: CallbackQuery, state: FSMContext):
    """Кнопка «Назад в главное меню»."""
    await state.clear()
    await callback.message.edit_text(
        "🏠 *Главное меню*\n\nВыбери действие:",
        reply_markup=get_main_menu(),
        parse_mode="Markdown",
    )
    await callback.answer()


# ═══════════════════════════════════════════════════════════════
# FALLBACK-ХЕНДЛЕР (для сообщений вне состояния)
# ═══════════════════════════════════════════════════════════════

@dp.message(F.text & ~F.text.startswith("/"))
async def handle_unknown(message: Message, state: FSMContext):
    """
    Ловит сообщения, которые не попали в другие хендлеры.
    ВАЖНО: этот хендлер в самом низу, чтобы не перехватывать
    сообщения агентов.
    """
    current_state = await state.get_state()
    if current_state is not None:
        # Есть активное состояние — не мешаем
        return

    await message.answer(
        "🤔 Не понял команду.\n\n"
        "Отправь /agents, чтобы выбрать AI-агента, "
        "или /help для справки."
    )


# ═══════════════════════════════════════════════════════════════
# ПОДКЛЮЧАЕМ РОУТЕР АГЕНТОВ
# ═══════════════════════════════════════════════════════════════
# ВАЖНО: подключаем роутер агентов ПОСЛЕ базовых хендлеров,
# чтобы команды /start, /help не перехватывались агентами,
# но ДО fallback-хендлера handle_unknown.

dp.include_router(agents_router)


# ═══════════════════════════════════════════════════════════════
# УСТАНОВКА КОМАНД
# ═══════════════════════════════════════════════════════════════

async def _set_bot_commands() -> None:
    """Установить список команд в Telegram."""
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
    """Точка входа: инициализация и запуск polling."""
    logger.info("═" * 55)
    logger.info("  🤖 Telegram Bot with AI Agents")
    logger.info("═" * 55)

    # 1. Проверяем настройки
    _validate_settings()

    # 2. Инициализируем БД (если есть)
    await _init_database()

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

    # 5. Удаляем вебхук (на случай, если был)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logger.debug(f"delete_webhook: {e}")

    # 6. Запускаем polling
    logger.info("🚀 Бот запущен. Ctrl+C — остановка.\n")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        await bot.session.close()
        logger.info("👋 Бот остановлен")


def run() -> None:
    """Обёртка с обработкой Ctrl+C."""
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Получен сигнал остановки")
    except Exception as e:
        logger.exception(f"❌ Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run()
