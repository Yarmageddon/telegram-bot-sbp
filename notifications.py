"""
Notification system for subscription reminders
"""
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import and_
from models import SessionLocal, Subscription, User
from config import settings


async def check_expiring_subscriptions():
    """Check and notify users about expiring subscriptions"""
    db = SessionLocal()
    try:
        # Подписки, которые истекают через 3 дня
        three_days_later = datetime.now() + timedelta(days=3)
        expiring_soon = db.query(Subscription).filter(
            and_(
                Subscription.active == True,
                Subscription.expires_at <= three_days_later,
                Subscription.expires_at > datetime.now()
            )
        ).all()
        
        from bot import bot
        
        for subscription in expiring_soon:
            user = db.query(User).filter(User.id == subscription.user_id).first()
            if user:
                days_left = (subscription.expires_at - datetime.now()).days
                
                message = (
                    f"⏰ <b>Ваша подписка скоро истекает!</b>\n\n"
                    f"Осталось <b>{days_left} дней</b>.\n\n"
                    f"Продлите подписку, чтобы не потерять доступ ко всем функциям:\n"
                    f"• Все возможности сервиса\n"
                    f"• Приоритетная поддержка\n"
                    f"• Регулярные обновления\n\n"
                    f"Используйте команду /subscribe для продления."
                )
                
                try:
                    await bot.send_message(
                        user.telegram_id,
                        message,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    print(f"Error sending notification to {user.telegram_id}: {e}")
        
        # Подписки, которые истекают сегодня
        today = datetime.now().replace(hour=23, minute=59, second=59)
        expiring_today = db.query(Subscription).filter(
            and_(
                Subscription.active == True,
                Subscription.expires_at <= today,
                Subscription.expires_at > datetime.now()
            )
        ).all()
        
        for subscription in expiring_today:
            user = db.query(User).filter(User.id == subscription.user_id).first()
            if user:
                message = (
                    f"🚨 <b>Ваша подписка истекает сегодня!</b>\n\n"
                    f"Продлите подписку прямо сейчас, чтобы не потерять доступ.\n\n"
                    f"Используйте команду /subscribe"
                )
                
                try:
                    await bot.send_message(
                        user.telegram_id,
                        message,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    print(f"Error sending notification to {user.telegram_id}: {e}")
    
    finally:
        db.close()


async def notification_scheduler():
    """Scheduler for sending notifications"""
    while True:
        try:
            await check_expiring_subscriptions()
        except Exception as e:
            print(f"Error in notification scheduler: {e}")
        
        # Проверяем каждые 6 часов
        await asyncio.sleep(6 * 60 * 60)
