"""
Личный кабинет пользователя
"""
from datetime import datetime
from models import SessionLocal, User, Subscription, Payment
from models_v2 import PersonalStats


def get_account_info(user_id: int) -> dict:
    """Получить информацию об аккаунте"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        
        subscription = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.active == True,
            Subscription.expires_at > datetime.now()
        ).first()
        
        stats = db.query(PersonalStats).filter(PersonalStats.user_id == user_id).first()
        
        return {
            "user": user,
            "subscription": subscription,
            "stats": stats
        }
    finally:
        db.close()


def format_account_info(info: dict) -> str:
    """Форматировать информацию об аккаунте"""
    user = info["user"]
    subscription = info["subscription"]
    stats = info["stats"]
    
    text = f"👤 <b>Личный кабинет</b>\n\n"
    text += f"<b>Имя:</b> {user.first_name or 'Не указано'}\n"
    text += f"<b>Username:</b> @{user.username or 'Не указан'}\n"
    text += f"<b>Регистрация:</b> {user.created_at.strftime('%d.%m.%Y')}\n\n"
    
    if subscription:
        days_left = (subscription.expires_at - datetime.now()).days
        text += f"💎 <b>Подписка:</b> {subscription.plan}\n"
        text += f"⏳ <b>Осталось дней:</b> {days_left}\n"
        text += f"📅 <b>Действует до:</b> {subscription.expires_at.strftime('%d.%m.%Y')}\n\n"
    else:
        text += "💎 <b>Подписка:</b> Не активна\n\n"
    
    if stats:
        text += "📊 <b>Статистика:</b>\n"
        text += f"• Документов обработано: {stats.documents_converted}\n"
        text += f"• OCR распознаваний: {stats.ocr_processed}\n"
        text += f"• Отзывов оставлено: {stats.reviews_given}\n"
        text += f"• Рефералов приглашено: {stats.referrals_count}\n"
    
    return text


def get_payment_history(user_id: int) -> list:
    """Получить историю платежей"""
    db = SessionLocal()
    try:
        return db.query(Payment).filter(Payment.user_id == user_id).order_by(Payment.created_at.desc()).all()
    finally:
        db.close()


def format_payment_history(payments: list) -> str:
    """Форматировать историю платежей"""
    if not payments:
        return "📋 История платежей пуста"
    
    text = "💳 <b>История платежей</b>\n\n"
    for payment in payments[:10]:  # Последние 10 платежей
        status_emoji = "✅" if payment.status == "completed" else "⏳"
        text += f"{status_emoji} {payment.amount} {payment.currency} - {payment.created_at.strftime('%d.%m.%Y')}\n"
    
    return text


def update_stats(user_id: int, field: str, increment: int = 1):
    """Обновить статистику пользователя"""
    db = SessionLocal()
    try:
        stats = db.query(PersonalStats).filter(PersonalStats.user_id == user_id).first()
        
        if not stats:
            stats = PersonalStats(user_id=user_id)
            db.add(stats)
        
        if field == "documents_converted":
            stats.documents_converted += increment
        elif field == "ocr_processed":
            stats.ocr_processed += increment
        elif field == "reviews_given":
            stats.reviews_given += increment
        elif field == "referrals_count":
            stats.referrals_count += increment
        
        stats.last_activity = datetime.now()
        db.commit()
    finally:
        db.close()
