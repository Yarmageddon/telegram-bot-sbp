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
                    f"Используйте команду /subscribe для продления."
                )
                try:
                    await bot.send_message(user.telegram_id, message, parse_mode="HTML")
                except Exception as e:
                    print(f"Error sending notification: {e}")
    finally:
        db.close()


async def notification_scheduler():
    """Scheduler for sending notifications"""
    while True:
        try:
            await check_expiring_subscriptions()
        except Exception as e:
            print(f"Error in notification scheduler: {e}")
        await asyncio.sleep(6 * 60 * 60)
