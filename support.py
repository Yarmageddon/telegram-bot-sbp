"""
Support ticket system
"""
from datetime import datetime
from models_extended import SupportTicket
from models import SessionLocal


def create_support_ticket(user_id: int, message: str) -> int:
    """Create new support ticket"""
    db = SessionLocal()
    try:
        ticket = SupportTicket(user_id=user_id, message=message, status="open")
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        return ticket.id
    finally:
        db.close()


def get_user_tickets(user_id: int) -> list:
    """Get all tickets for user"""
    db = SessionLocal()
    try:
        return db.query(SupportTicket).filter(
            SupportTicket.user_id == user_id
        ).order_by(SupportTicket.created_at.desc()).all()
    finally:
        db.close()


def get_all_open_tickets() -> list:
    """Get all open tickets for admin"""
    db = SessionLocal()
    try:
        return db.query(SupportTicket).filter(
            SupportTicket.status.in_(["open", "in_progress"])
        ).order_by(SupportTicket.created_at.asc()).all()
    finally:
        db.close()


def respond_to_ticket(ticket_id: int, admin_response: str) -> bool:
    """Admin responds to ticket"""
    db = SessionLocal()
    try:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket:
            return False
        ticket.admin_response = admin_response
        ticket.status = "in_progress"
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        return False
    finally:
        db.close()


def close_ticket(ticket_id: int) -> bool:
    """Close support ticket"""
    db = SessionLocal()
    try:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if not ticket:
            return False
        ticket.status = "closed"
        ticket.closed_at = datetime.now()
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        return False
    finally:
        db.close()
