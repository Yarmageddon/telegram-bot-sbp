"""
Личный кабинет - статистика, история платежей
"""
from datetime import datetime
from models import SessionLocal, User, Subscription, Payment
from models_v2 import PersonalStats, Review
from models_extended import Referral


def get_or_create_stats(user_id: int) -> PersonalStats:
    """Получить или создать статистику пользователя"""
    db = SessionLocal()
    try:
        stats = db.query(PersonalStats).filter(PersonalStats.user_id == user_id).first()
        
        if not stats:
            stats = PersonalStats(user_id=user_id)
            db.add(stats)
            db.commit()
            db.refresh(stats)
        
        return stats
    finally:
        db.close()


def update_stats(user_id: int, **kwargs):
    """Обновить статистику пользователя"""
    db = SessionLocal()
    try:
        stats = db.query(PersonalStats).filter(PersonalStats.user_id == user_id).first()
        
        if not stats:
            stats = PersonalStats(user_id=user_id)
            db.add(stats)
        
        for key, value in kwargs.items():
            if hasattr(stats, key):
                setattr(stats, key, value)
        
        stats.last_activity = datetime.now()
        db.commit()
    
    except Exception as e:
        db.rollback()
        print(f"Error updating stats: {e}")
    
    finally:
        db.close()


def get_payment_history(user_id: int, limit: int = 10) -> list:
    """Получить историю платежей"""
    db = SessionLocal()
    try:
        payments = db.query(Payment).filter(
            Payment.user_id == user_id
        ).order_by(Payment.created_at.desc()).limit(limit).all()
        return payments
    finally:
        db.close()


def get_account_info(user_id: int) -> dict:
    """Получить полную информацию для личного кабинета"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        
        # Текущая подписка
        subscription = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.active == True,
            Subscription.expires_at > datetime.now()
        ).order_by(Subscription.started_at.desc()).first()
        
        # Статистика платежей
        payments = db.query(Payment).filter(
            Payment.user_id == user_id,
            Payment.status == "completed"
        ).all()
        total_spent = sum(p.amount for p in payments) / 100  # в рублях
        
        # Статистика отзывов
        reviews_count = db.query(Review).filter(Review.user_id == user_id).count()
        
        # Рефералы
        referrals_count = db.query(Referral).filter(
            Referral.referrer_id == user_id,
            Referral.referred_id != user_id
        ).count()
        
        # Регистрация
        registered_days = (datetime.now() - user.created_at).days if user.created_at else 0
        
        return {
            "username": user.username or f"ID{user.telegram_id}",
            "telegram_id": user.telegram_id,
            "registered_days": registered_days,
            "subscription": {
                "plan": subscription.plan if subscription else None,
                "expires_at": subscription.expires_at if subscription else None,
                "days_left": (subscription.expires_at - datetime.now()).days if subscription else 0,
                "active": subscription is not None
            },
            "total_spent": total_spent,
            "payments_count": len(payments),
            "reviews_count": reviews_count,
            "referrals_count": referrals_count
        }
    
    finally:
        db.close()


def format_account_info(info: dict) -> str:
    """Форматировать информацию для вывода"""
    if not info:
        return "❌ Информация не найдена"
    
    text = (
        f"👤 <b>Личный кабинет</b>\n\n"
        f"🆔 <b>Telegram ID:</b> <code>{info['telegram_id']}</code>\n"
        f"📅 <b>С нами:</b> {info['registered_days']} дней\n\n"
    )
    
    if info['subscription']['active']:
        text += (
            f"💎 <b>Подписка:</b> {info['subscription']['plan']}\n"
            f"🕒 <b>Действует до:</b> {info['subscription']['expires_at'].strftime('%d.%m.%Y')}\n"
            f"⏳ <b>Осталось дней:</b> {info['subscription']['days_left']}\n\n"
        )
    else:
        text += "💎 <b>Подписка:</b> не активна\n\n"
    
    text += (
        f"📊 <b>Статистика:</b>\n"
        f"💰 <b>Потрачено:</b> {info['total_spent']:.0f} ₽\n"
        f"💳 <b>Платежей:</b> {info['payments_count']}\n"
        f"⭐ <b>Отзывов:</b> {info['reviews_count']}\n"
        f"👥 <b>Рефералов:</b> {info['referrals_count']}\n"
    )
    
    return text


def format_payment_history(payments: list) -> str:
    """Форматировать историю платежей"""
    if not payments:
        return "📋 История платежей пуста"
    
    text = "💳 <b>История платежей:</b>\n\n"
    
    for payment in payments[:10]:
        status_emoji = {
            "completed": "✅",
            "pending": "⏳",
            "failed": "❌"
        }.get(payment.status, "⚪")
        
        text += (
            f"{status_emoji} <b>{payment.amount / 100:.0f} ₽</b>\n"
            f"📅 {payment.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"📝 {payment.payload or '—'}\n\n"
        )
    
    return text
