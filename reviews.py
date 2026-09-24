"""
Система отзывов и рейтингов
"""
from datetime import datetime
from models import SessionLocal
from models_v2 import Review


def create_review(user_id: int, rating: int, text: str = None, category: str = None, suggestion: str = None) -> dict:
    """Создать отзыв"""
    db = SessionLocal()
    try:
        review = Review(
            user_id=user_id,
            rating=rating,
            text=text,
            category=category,
            suggestion=suggestion
        )
        db.add(review)
        db.commit()
        return {"success": True, "message": "Спасибо за ваш отзыв!"}
    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Ошибка: {str(e)}"}
    finally:
        db.close()


def get_user_reviews(user_id: int) -> list:
    """Получить отзывы пользователя"""
    db = SessionLocal()
    try:
        return db.query(Review).filter(Review.user_id == user_id).all()
    finally:
        db.close()


def get_rating_stats() -> dict:
    """Получить статистику рейтингов"""
    db = SessionLocal()
    try:
        reviews = db.query(Review).all()
        if not reviews:
            return {"total": 0, "average": 0, "distribution": {}}
        
        total = len(reviews)
        average = sum(r.rating for r in reviews) / total
        
        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for review in reviews:
            distribution[review.rating] += 1
        
        return {
            "total": total,
            "average": round(average, 2),
            "distribution": distribution
        }
    finally:
        db.close()
