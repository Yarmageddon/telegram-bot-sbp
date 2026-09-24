"""
Апгрейд/даунгрейд тарифов
"""
from datetime import datetime, timedelta
from models import SessionLocal, Subscription, User
from models_v2 import SubscriptionPlan


def get_all_plans() -> list:
    """Получить все активные тарифы"""
    db = SessionLocal()
    try:
        plans = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.active == True
        ).order_by(SubscriptionPlan.level).all()
        return plans
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
        ).order_by(Subscription.started_at.desc()).first()
        
        if not subscription:
            return {"plan": None, "level": 0}
        
        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.name == subscription.plan
        ).first()
        
        return {
            "plan": subscription.plan,
            "level": plan.level if plan else 0,
            "expires_at": subscription.expires_at,
            "days_left": (subscription.expires_at - datetime.now()).days
        }
    
    finally:
        db.close()


def upgrade_subscription(user_id: int, new_plan_name: str) -> tuple[bool, str]:
    """Апгрейд подписки (переход на более высокий тариф)"""
    db = SessionLocal()
    try:
        # Находим текущую подписку
        current_sub = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.active == True,
            Subscription.expires_at > datetime.now()
        ).order_by(Subscription.started_at.desc()).first()
        
        if not current_sub:
            return False, "❌ У вас нет активной подписки"
        
        # Находим текущий и новый тариф
        current_plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.name == current_sub.plan
        ).first()
        
        new_plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.name == new_plan_name
        ).first()
        
        if not new_plan:
            return False, "❌ Тариф не найден"
        
        if not current_plan:
            return False, "❌ Текущий тариф не найден"
        
        if new_plan.level <= current_plan.level:
            return False, "❌ Это не апгрейд. Используйте даунгрейд"
        
        # Пересчитываем оставшиеся дни
        days_left = (current_sub.expires_at - datetime.now()).days
        
        # Деактивируем старую подписку
        current_sub.active = False
        
        # Создаем новую подписку с сохранением оставшихся дней
        new_sub = Subscription(
            user_id=user_id,
            plan=new_plan_name,
            expires_at=datetime.now() + timedelta(days=days_left),
            active=True
        )
        db.add(new_sub)
        
        db.commit()
        
        return True, f"✅ Подписка обновлена до тарифа '{new_plan_name}'"
    
    except Exception as e:
        db.rollback()
        return False, f"❌ Ошибка: {str(e)}"
    
    finally:
        db.close()


def downgrade_subscription(user_id: int, new_plan_name: str) -> tuple[bool, str]:
    """Даунгрейд подписки (переход на более низкий тариф)"""
    db = SessionLocal()
    try:
        current_sub = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.active == True,
            Subscription.expires_at > datetime.now()
        ).order_by(Subscription.started_at.desc()).first()
        
        if not current_sub:
            return False, "❌ У вас нет активной подписки"
        
        current_plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.name == current_sub.plan
        ).first()
        
        new_plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.name == new_plan_name
        ).first()
        
        if not new_plan:
            return False, "❌ Тариф не найден"
        
        if not current_plan:
            return False, "❌ Текущий тариф не найден"
        
        if new_plan.level >= current_plan.level:
            return False, "❌ Это не даунгрейд. Используйте апгрейд"
        
        # Даунгрейд применяется после окончания текущей подписки
        days_left = (current_sub.expires_at - datetime.now()).days
        
        return True, (
            f"✅ Даунгрейд запланирован!\n\n"
            f"После окончания текущего тарифа ({days_left} дн.)\n"
            f"вы автоматически перейдете на тариф '{new_plan_name}'"
        )
    
    except Exception as e:
        return False, f"❌ Ошибка: {str(e)}"
    
    finally:
        db.close()
