"""
Promo codes system
"""
from datetime import datetime, timedelta
from models_extended import PromoCode, PromoCodeUsage
from models import SessionLocal


def create_promo_code(code: str, discount_percent: int, max_uses: int = 1, 
                      expires_days: int = None) -> PromoCode:
    """Create new promo code"""
    db = SessionLocal()
    try:
        expires_at = None
        if expires_days:
            expires_at = datetime.now() + timedelta(days=expires_days)
        
        promo = PromoCode(
            code=code.upper(),
            discount_percent=discount_percent,
            max_uses=max_uses,
            expires_at=expires_at
        )
        db.add(promo)
        db.commit()
        db.refresh(promo)
        return promo
    finally:
        db.close()


def validate_promo_code(code: str, user_id: int) -> tuple:
    """Validate promo code"""
    db = SessionLocal()
    try:
        promo = db.query(PromoCode).filter(PromoCode.code == code.upper()).first()
        
        if not promo:
            return False, "❌ Промокод не найден", None
        
        if not promo.is_valid:
            return False, "❌ Промокод недействителен", None
        
        existing_usage = db.query(PromoCodeUsage).filter(
            PromoCodeUsage.promo_code_id == promo.id,
            PromoCodeUsage.user_id == user_id
        ).first()
        
        if existing_usage:
            return False, "❌ Вы уже использовали этот промокод", None
        
        return True, "✅ Промокод действителен", promo
    finally:
        db.close()


def use_promo_code(code: str, user_id: int) -> tuple:
    """Use promo code"""
    db = SessionLocal()
    try:
        promo = db.query(PromoCode).filter(PromoCode.code == code.upper()).first()
        if not promo or not promo.is_valid:
            return False, "Промокод недействителен"
        
        usage = PromoCodeUsage(promo_code_id=promo.id, user_id=user_id)
        db.add(usage)
        promo.used_count += 1
        db.commit()
        
        return True, f"✅ Промокод применен! Скидка {promo.discount_percent}%"
    except Exception as e:
        db.rollback()
        return False, f"Ошибка: {str(e)}"
    finally:
        db.close()


def get_all_promo_codes() -> list:
    """Get all promo codes"""
    db = SessionLocal()
    try:
        return db.query(PromoCode).all()
    finally:
        db.close()
