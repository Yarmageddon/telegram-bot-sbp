"""
Триал-периоды
"""
from datetime import datetime, timedelta
from models import SessionLocal
from models_v2 import Trial


def start_trial(user_id: int, days: int = 7) -> dict:
    """Активировать триал-период"""
    db = SessionLocal()
    try:
        # Проверяем, не использовал ли пользователь триал
        existing = db.query(Trial).filter(Trial.user_id == user_id).first()
        if existing and existing.used:
            return {"success": False, "message": "Триал уже использован"}
        
        # Создаем новый триал
        trial = Trial(
            user_id=user_id,
            expires_at=datetime.now() + timedelta(days=days),
            used=True
        )
        
        if existing:
            existing.expires_at = datetime.now() + timedelta(days=days)
            existing.used = True
        else:
            db.add(trial)
        
        db.commit()
        return {"success": True, "message": f"Триал активирован на {days} дней", "days_left": days}
    finally:
        db.close()


def check_trial_status(user_id: int) -> dict:
    """Проверить статус триала"""
    db = SessionLocal()
    try:
        trial = db.query(Trial).filter(Trial.user_id == user_id).first()
        if not trial:
            return {"used": False, "active": False, "days_left": 0}
        
        if not trial.used:
            return {"used": False, "active": False, "days_left": 0}
        
        days_left = (trial.expires_at - datetime.now()).days
        active = days_left > 0
        
        return {
            "used": True,
            "active": active,
            "days_left": max(0, days_left),
            "expires_at": trial.expires_at
        }
    finally:
        db.close()
