"""
Триал-периоды
"""
from datetime import datetime, timedelta
from models import SessionLocal, User, Subscription
from models_v2 import Trial


def start_trial(user_id: int, days: int = 7) -> tuple[bool, str]:
    """Начать триал-период для пользователя"""
    db = SessionLocal()
    try:
        # Проверяем, не был ли уже триал
        existing = db.query(Trial).filter(Trial.user_id == user_id).first()
        if existing:
            return False, "❌ Вы уже использовали триал-период"
        
        # Проверяем, нет ли активной подписки
        active_sub = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.active == True,
            Subscription.expires_at > datetime.now()
        ).first()
        if active_sub:
            return False, "❌ У вас уже есть активная подписка"
        
        # Создаем триал
        trial = Trial(
            user_id=user_id,
            expires_at=datetime.now() + timedelta(days=days),
            activated=True
        )
        db.add(trial)
        
        # Создаем подписку на триал
        subscription = Subscription(
            user_id=user_id,
            plan="trial",
            expires_at=datetime.now() + timedelta(days=days),
            active=True
        )
        db.add(subscription)
        
        db.commit()
        
        return True, f"✅ Триал-период {days} дней активирован!"
    
    except Exception as e:
        db.rollback()
        return False, f"❌ Ошибка: {str(e)}"
    
    finally:
        db.close()


def check_trial_status(user_id: int) -> dict:
    """Проверить статус триала"""
    db = SessionLocal()
    try:
        trial = db.query(Trial).filter(Trial.user_id == user_id).first()
        
        if not trial:
            return {"has_trial": False, "used": False}
        
        days_left = max(0, (trial.expires_at - datetime.now()).days)
        
        return {
            "has_trial": True,
            "used": True,
            "days_left": days_left,
            "expires_at": trial.expires_at,
            "converted": trial.converted_to_paid
        }
    
    finally:
        db.close()


def convert_trial_to_paid(user_id: int) -> bool:
    """Отметить, что триал конвертирован в платную подписку"""
    db = SessionLocal()
    try:
        trial = db.query(Trial).filter(Trial.user_id == user_id).first()
        if trial:
            trial.converted_to_paid = True
            db.commit()
            return True
        return False
    finally:
        db.close()
