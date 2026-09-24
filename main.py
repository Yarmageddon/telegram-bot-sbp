"""
Точка входа для Railway
"""
import asyncio
import logging
from models import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("🚀 Starting Telegram Bot on Railway...")
    
    # Инициализация БД
    init_db()
    logger.info("✅ Database initialized")
    
    # Импорт и запуск бота
    from bot_v2 import bot, dp
    from aiogram.types import BotCommand
    
    # Установка команд бота
    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="account", description="Личный кабинет"),
        BotCommand(command="subscribe", description="Оформить подписку"),
        BotCommand(command="trial", description="Активировать триал"),
        BotCommand(command="support", description="Поддержка")
    ])
    
    # Удаление вебхука и запуск polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
