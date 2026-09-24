"""
Отзывы, рейтинги и предложения
"""
from datetime import datetime
from models import SessionLocal, User
from models_v2 import Review


def create_review(user_id: int, rating: int, text: str = None, 
                  suggestion: str = None, category: str = "general") -> int:
    """Создать отзыв"""
    db = SessionLocal()
    try:
        review = Review(
            user_id=user_id,
            rating=rating,
            text=text,
            suggestion=suggestion,
            category=category
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        return review.id
    finally:
        db.close()


def get_user_reviews(user_id: int) -> list:
    """Получить отзывы пользователя"""
    db = SessionLocal()
    try:
        reviews = db.query(Review).filter(
            Review.user_id == user_id
        ).order_by(Review.created_at.desc()).all()
        return reviews
    finally:
        db.close()


def get_all_reviews(limit: int = 10) -> list:
    """Получить все отзывы (для админов)"""
    db = SessionLocal()
    try:
        reviews = db.query(Review).order_by(
            Review.created_at.desc()
        ).limit(limit).all()
        return reviews
    finally:
        db.close()


def get_average_rating() -> float:
    """Получить средний рейтинг"""
    db = SessionLocal()
    try:
        reviews = db.query(Review).all()
        if not reviews:
            return 0.0
        return sum(r.rating for r in reviews) / len(reviews)
    finally:
        db.close()


def respond_to_review(review_id: int, response: str) -> bool:
    """Ответить на отзыв"""
    db = SessionLocal()
    try:
        review = db.query(Review).filter(Review.id == review_id).first()
        if not review:
            return False
        
        review.admin_response = response
        review.responded_at = datetime.now()
        db.commit()
        return True
    finally:
        db.close()


def get_rating_stats() -> dict:
    """Статистика по рейтингам"""
    db = SessionLocal()
    try:
        reviews = db.query(Review).all()
        
        stats = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for review in reviews:
            if review.rating in stats:
                stats[review.rating] += 1
        
        total = len(reviews)
        avg = sum(r.rating for r in reviews) / total if total > 0 else 0
        
        return {
            "total": total,
            "average": round(avg, 2),
            "distribution": stats
        }
    finally:
        db.close()
