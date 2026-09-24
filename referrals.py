"""
Referral system
"""
import uuid
from datetime import datetime, timedelta
from models_extended import Referral
from models import SessionLocal, User, Subscription


def generate_referral_code(user_id: int) -> str:
    """Generate unique referral code"""
    return f"REF{user_id}{uuid.uuid4().hex[:8].upper()}"


def get_or_create_referral_code(user_id: int) -> str:
    """Get existing or create new referral code"""
    db = SessionLocal()
    try:
        referral = db.query(Referral).filter(
            Referral.referrer_id == user_id,
            Referral.referred_id == user_id
        ).first()
        
        if referral:
            return referral.referral_code
        
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


def get_user_referrals(user_id: int) -> list:
    """Get all referrals for user"""
    db = SessionLocal()
    try:
        return db.query(Referral).filter(
            Referral.referrer_id == user_id,
            Referral.referred_id != user_id
        ).all()
    finally:
        db.close()
