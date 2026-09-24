"""
Telegram Bot - Main entry point for Railway deployment
"""
import asyncio
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main function for Railway deployment"""
    logger.info("🚀 Starting Telegram Bot on Railway...")
    
    # Import bot module
    from bot_v2 import bot, dp
    from models import init_db
    from config import settings
    
    logger.info(f"✅ Bot initialized")
    logger.info(f" Admin IDs: {settings.ADMIN_IDS}")
    
    # Initialize database
    init_db()
    logger.info("✅ Database initialized")
    
    # Start polling
    logger.info("🔄 Starting polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
