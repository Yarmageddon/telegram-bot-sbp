"""
Система уведомлений
"""
import asyncio
from datetime import datetime, timedelta
from models import SessionLocal, Subscription, User


async def check_expiring_subscriptions():
    """Проверка истекающих подписок"""
    db = SessionLocal()
    try:
        # Подписки, истекающие через 3 дня
        three_days_later = datetime.now() + timedelta(days=3)
        expiring = db.query(Subscription).filter(
            Subscription.active == True,
            Subscription.expires_at <= three_days_later,
            Subscription.expires_at > datetime.now()
        ).all()
        
        for sub in expiring:
            user = db.query(User).filter(User.id == sub.user_id).first()
            if user:
                days_left = (sub.expires_at - datetime.now()).days
                print(f"Уведомление для пользователя {user.telegram_id}: подписка истекает через {days_left} дней")
                # Здесь можно добавить отправку уведомления через бота
    finally:
        db.close()


async def notification_scheduler():
    """Планировщик уведомлений"""
    while True:
        await check_expiring_subscriptions()
        await asyncio.sleep(24 * 60 * 60)  # Раз в сутки
