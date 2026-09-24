"""
Функции работы с базой данных
"""
from datetime import datetime, timedelta
from models import SessionLocal, User, Subscription, Payment


def get_or_create_user(db, telegram_id, username=None, first_name=None, last_name=None):
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


def get_active_subscription(db, user_id):
    return db.query(Subscription).filter(
        Subscription.user_id == user_id,
        Subscription.active == True,
        Subscription.expires_at > datetime.now()
    ).first()


def create_payment(db, user_id, amount):
    payment = Payment(user_id=user_id, amount=amount)
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment
