"""
Referral system
"""
import uuid
from datetime import datetime, timedelta
from models_extended import Referral
from models import SessionLocal, User, Subscription


def generate_referral_code(user_id: int) -> str:
    """Generate unique referral code for user"""
    code = f"REF{user_id}{uuid.uuid4().hex[:8].upper()}"
    return code


def get_or_create_referral_code(user_id: int) -> str:
    """Get existing or create new referral code"""
    db = SessionLocal()
    try:
        # Проверяем, есть ли уже код
        referral = db.query(Referral).filter(Referral.referrer_id == user_id).first()
        
        if referral:
            return referral.referral_code
        
        # Создаем новый код
        code = generate_referral_code(user_id)
        new_referral = Referral(
            referrer_id=user_id,
            referred_id=user_id,
            referral_code=code,
            activated=True
        )
        db.add(new_referral)
        db.commit()
        
        return code
    
    finally:
        db.close()


def register_referral(referrer_user_id: int, referred_user_id: int) -> tuple[bool, str]:
    """Register new referral"""
    db = SessionLocal()
    try:
        # Проверяем, не был ли уже зарегистрирован
        existing = db.query(Referral).filter(
            Referral.referred_id == referred_user_id,
            Referral.referrer_id != referred_user_id
        ).first()
        
        if existing:
            return False, "Вы уже были приглашены"
        
        # Находим реферера
        referrer_referral = db.query(Referral).filter(
            Referral.referrer_id == referrer_user_id,
            Referral.activated == True
        ).first()
        
        if not referrer_referral:
            return False, "Неверный реферальный код"
        
        # Создаем запись о реферале
        new_referral = Referral(
            referrer_id=referrer_user_id,
            referred_id=referred_user_id,
            referral_code=referrer_referral.referral_code,
            bonus_days=7,
            activated=False
        )
        db.add(new_referral)
        db.commit()
        
        return True, "✅ Реферал зарегистрирован!"
    
    except Exception as e:
        db.rollback()
        return False, f"Ошибка: {str(e)}"
    
    finally:
        db.close()


def activate_referral_bonus(referred_user_id: int) -> tuple[bool, str]:
    """Activate bonus for referrer when referred user makes first payment"""
    db = SessionLocal()
    try:
        # Находим реферала
        referral = db.query(Referral).filter(
            Referral.referred_id == referred_user_id,
            Referral.activated == False
        ).first()
        
        if not referral:
            return False, "Реферал не найден"
        
        # Активируем бонус
        referral.activated = True
        
        # Добавляем бонусные дни пригласившему
        referrer_subscription = db.query(Subscription).filter(
            Subscription.user_id == referral.referrer_id,
            Subscription.active == True
        ).order_by(Subscription.started_at.desc()).first()
        
        if referrer_subscription:
            # Продлеваем подписку на бонусные дни
            referrer_subscription.expires_at += timedelta(days=referral.bonus_days)
        
        db.commit()
        
        return True, f"✅ Бонус {referral.bonus_days} дней активирован!"
    
    except Exception as e:
        db.rollback()
        return False, f"Ошибка: {str(e)}"
    
    finally:
        db.close()


def get_user_referrals(user_id: int) -> list:
    """Get all referrals for user"""
    db = SessionLocal()
    try:
        referrals = db.query(Referral).filter(
            Referral.referrer_id == user_id,
            Referral.referred_id != user_id
        ).all()
        return referrals
    finally:
        db.close()
