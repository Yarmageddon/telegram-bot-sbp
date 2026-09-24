"""
Апгрейд/даунгрейд подписок
"""
from datetime import datetime, timedelta
from models import SessionLocal, Subscription
from models_v2 import SubscriptionPlan


def get_all_plans() -> list:
    """Получить все доступные тарифы"""
    db = SessionLocal()
    try:
        return db.query(SubscriptionPlan).filter(SubscriptionPlan.active == True).all()
    finally:
        db.close()


def get_current_plan(user_id: int) -> dict:
    """Получить текущий тариф пользователя"""
    db = SessionLocal()
    try:
        subscription = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.active == True,
            Subscription.expires_at > datetime.now()
        ).first()
        
        if not subscription:
            return {"active": False}
        
        return {
            "active": True,
            "plan": subscription.plan,
            "expires_at": subscription.expires_at,
            "days_left": (subscription.expires_at - datetime.now()).days
        }
    finally:
        db.close()


def upgrade_subscription(user_id: int, new_plan: str, duration_days: int = 30) -> dict:
    """Сменить тариф подписки"""
    db = SessionLocal()
    try:
        # Деактивируем текущую подписку
        current = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.active == True
        ).first()
        
        if current:
            current.active = False
        
        # Создаем новую подписку
        new_subscription = Subscription(
            user_id=user_id,
            plan=new_plan,
            starts_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=duration_days),
            active=True
        )
        db.add(new_subscription)
        db.commit()
        
        return {"success": True, "message": f"Тариф изменен на {new_plan}"}
    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Ошибка: {str(e)}"}
    finally:
        db.close()
