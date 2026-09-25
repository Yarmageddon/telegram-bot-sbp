"""
Database helpers — все операции с БД в одном месте
"""
from datetime import datetime, timedelta
from models import SessionLocal, User, Subscription, Payment, Trial, Review, SupportTicket, NewsPost
import uuid


# ── Пользователи ────────────────────────────────────────────────────────────

def get_or_create_user(telegram_id: int, username=None, first_name=None, last_name=None) -> User:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            ref_code = f"REF{telegram_id}{uuid.uuid4().hex[:6].upper()}"
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                referral_code=ref_code,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user.last_seen = datetime.now()
            if username:
                user.username = username
            db.commit()
            db.refresh(user)
        return user
    finally:
        db.close()


def get_user_by_ref_code(code: str):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.referral_code == code).first()
    finally:
        db.close()


def apply_referral(new_user_id: int, referrer_id: int):
    """Зачислить реферальный бонус пригласившему."""
    db = SessionLocal()
    try:
        new_user = db.query(User).filter(User.id == new_user_id).first()
        if new_user and not new_user.referred_by:
            new_user.referred_by = referrer_id
            db.commit()
    finally:
        db.close()


def get_all_users():
    db = SessionLocal()
    try:
        return db.query(User).filter(User.is_active == True, User.is_banned == False).all()
    finally:
        db.close()


# ── Подписки ─────────────────────────────────────────────────────────────────

def get_active_subscription(user_id: int):
    db = SessionLocal()
    try:
        return db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.active == True,
            Subscription.expires_at > datetime.now(),
        ).first()
    finally:
        db.close()


def create_subscription(user_id: int, plan: str, days: int) -> Subscription:
    db = SessionLocal()
    try:
        # Деактивируем старые
        db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.active == True,
        ).update({"active": False})
        sub = Subscription(
            user_id=user_id,
            plan=plan,
            expires_at=datetime.now() + timedelta(days=days),
            active=True,
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)
        return sub
    finally:
        db.close()


# ── Платежи ──────────────────────────────────────────────────────────────────

def create_payment(user_id: int, amount: float, plan: str) -> Payment:
    db = SessionLocal()
    try:
        p = Payment(user_id=user_id, amount=amount, plan=plan, status="pending")
        db.add(p)
        db.commit()
        db.refresh(p)
        return p
    finally:
        db.close()


def complete_payment(payment_id: int) -> bool:
    db = SessionLocal()
    try:
        p = db.query(Payment).filter(Payment.id == payment_id).first()
        if not p:
            return False
        p.status = "completed"
        p.completed_at = datetime.now()
        db.commit()
        return True
    finally:
        db.close()


def get_pending_payments():
    db = SessionLocal()
    try:
        return db.query(Payment).filter(Payment.status == "pending").all()
    finally:
        db.close()


def get_user_payments(user_id: int):
    db = SessionLocal()
    try:
        return db.query(Payment).filter(
            Payment.user_id == user_id
        ).order_by(Payment.created_at.desc()).limit(10).all()
    finally:
        db.close()


# ── Триал ────────────────────────────────────────────────────────────────────

def start_trial(user_id: int, days: int = 7) -> dict:
    db = SessionLocal()
    try:
        existing = db.query(Trial).filter(Trial.user_id == user_id).first()
        if existing and existing.used:
            return {"success": False, "message": "Триал уже использован"}
        if existing:
            existing.expires_at = datetime.now() + timedelta(days=days)
            existing.used = True
        else:
            db.add(Trial(
                user_id=user_id,
                expires_at=datetime.now() + timedelta(days=days),
                used=True,
            ))
        db.commit()
        return {"success": True, "days": days}
    finally:
        db.close()


def get_trial(user_id: int):
    db = SessionLocal()
    try:
        return db.query(Trial).filter(Trial.user_id == user_id).first()
    finally:
        db.close()


# ── Отзывы ───────────────────────────────────────────────────────────────────

def create_review(user_id: int, rating: int, text: str = None, category: str = None):
    db = SessionLocal()
    try:
        r = Review(user_id=user_id, rating=rating, text=text, category=category)
        db.add(r)
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def get_rating_stats() -> dict:
    db = SessionLocal()
    try:
        reviews = db.query(Review).all()
        if not reviews:
            return {"total": 0, "average": 0.0}
        total = len(reviews)
        avg = round(sum(r.rating for r in reviews) / total, 1)
        return {"total": total, "average": avg}
    finally:
        db.close()


# ── Поддержка ────────────────────────────────────────────────────────────────

def create_ticket(user_id: int, message: str) -> SupportTicket:
    db = SessionLocal()
    try:
        t = SupportTicket(user_id=user_id, message=message)
        db.add(t)
        db.commit()
        db.refresh(t)
        return t
    finally:
        db.close()


def get_open_tickets():
    db = SessionLocal()
    try:
        return db.query(SupportTicket).filter(
            SupportTicket.status.in_(["open", "answered"])
        ).order_by(SupportTicket.created_at.asc()).all()
    finally:
        db.close()


def answer_ticket(ticket_id: int, response: str) -> bool:
    db = SessionLocal()
    try:
        t = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not t:
            return False
        t.admin_response = response
        t.status = "answered"
        t.answered_at = datetime.now()
        db.commit()
        return True
    finally:
        db.close()


# ── Новости / рассылка ───────────────────────────────────────────────────────

def create_news(title: str, content: str, urgent: bool, author_id: int) -> dict:
    db = SessionLocal()
    try:
        n = NewsPost(title=title, content=content, urgent=urgent, author_id=author_id)
        db.add(n)
        db.commit()
        return {"success": True, "id": n.id}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


# ── Статистика (для админа) ───────────────────────────────────────────────────

def get_bot_stats() -> dict:
    db = SessionLocal()
    try:
        total_users = db.query(User).count()
        active_subs = db.query(Subscription).filter(
            Subscription.active == True,
            Subscription.expires_at > datetime.now(),
        ).count()
        pending_payments = db.query(Payment).filter(Payment.status == "pending").count()
        total_revenue = db.query(Payment).filter(Payment.status == "completed").all()
        revenue = sum(p.amount for p in total_revenue)
        open_tickets = db.query(SupportTicket).filter(SupportTicket.status == "open").count()
        return {
            "total_users": total_users,
            "active_subs": active_subs,
            "pending_payments": pending_payments,
            "revenue": revenue,
            "open_tickets": open_tickets,
        }
    finally:
        db.close()
