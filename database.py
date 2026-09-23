from models import User, Subscription, Payment, SessionLocal
from datetime import datetime, timedelta
from typing import Optional


def get_or_create_user(db, telegram_id: int, username: str = None, 
                       first_name: str = None, last_name: str = None) -> User:
    """Get or create user"""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    return user


def create_payment(db, user_id: int, provider_tx_id: str, 
                   amount: int, currency: str, payload: str) -> Payment:
    """Create payment"""
    payment = Payment(
        user_id=user_id,
        provider_transaction_id=provider_tx_id,
        amount=amount,
        currency=currency,
        status="pending",
        payload=payload
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def complete_payment(db, provider_tx_id: str) -> Optional[Payment]:
    """Complete payment and activate subscription"""
    payment = db.query(Payment).filter(Payment.provider_transaction_id == provider_tx_id).first()
    
    if payment and payment.status == "pending":
        payment.status = "completed"
        db.commit()
        db.refresh(payment)
        
        # Create subscription
        expires_at = datetime.now() + timedelta(days=30)
        subscription = Subscription(
            user_id=payment.user_id,
            plan="monthly",
            expires_at=expires_at,
            active=True,
            payment_id=payment.id
        )
        db.add(subscription)
        db.commit()
        
        return payment
    
    return None


def get_active_subscription(db, user_id: int) -> Optional[Subscription]:
    """Get active subscription for user"""
    subscription = db.query(Subscription).filter(
        Subscription.user_id == user_id,
        Subscription.active == True
    ).order_by(Subscription.started_at.desc()).first()
    
    if subscription and subscription.is_active:
        return subscription
    
    return None
