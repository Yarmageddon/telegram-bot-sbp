"""
Extended models for bot features
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from models import Base


class PromoCode(Base):
    """Promo codes model"""
    __tablename__ = "promo_codes"
    
    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    discount_percent = Column(Integer, nullable=False)
    max_uses = Column(Integer, default=1)
    used_count = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    
    usages = relationship("PromoCodeUsage", back_populates="promo_code")
    
    @property
    def is_valid(self) -> bool:
        """Check if promo code is valid"""
        if not self.active:
            return False
        if self.used_count >= self.max_uses:
            return False
        if self.expires_at and datetime.now() > self.expires_at:
            return False
        return True


class PromoCodeUsage(Base):
    """Promo code usage history"""
    __tablename__ = "promo_code_usages"
    
    id = Column(Integer, primary_key=True)
    promo_code_id = Column(Integer, ForeignKey("promo_codes.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    used_at = Column(DateTime, default=datetime.now)
    
    promo_code = relationship("PromoCode", back_populates="usages")


class Referral(Base):
    """Referral system model"""
    __tablename__ = "referrals"
    
    id = Column(Integer, primary_key=True)
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    referred_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    referral_code = Column(String(50), unique=True, nullable=False, index=True)
    bonus_days = Column(Integer, default=7)
    created_at = Column(DateTime, default=datetime.now)
    activated = Column(Boolean, default=False)


class SupportTicket(Base):
    """Support tickets model"""
    __tablename__ = "support_tickets"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(20), default="open")
    admin_response = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    closed_at = Column(DateTime, nullable=True)
