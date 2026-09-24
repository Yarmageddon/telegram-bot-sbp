"""
Push-уведомления о срочных новостях
"""
from datetime import datetime
from models import SessionLocal, User
from models_v2 import NewsPost


def create_news(title: str, content: str, urgent: bool = False, created_by: int = None) -> int:
    """Создать новость"""
    db = SessionLocal()
    try:
        news = NewsPost(
            title=title,
            content=content,
            urgent=urgent,
            created_by=created_by
        )
        db.add(news)
        db.commit()
        db.refresh(news)
        return news.id
    finally:
        db.close()


async def broadcast_news(bot, news_id: int) -> tuple[int, int]:
    """Разослать новость всем пользователям"""
    db = SessionLocal()
    try:
        news = db.query(NewsPost).filter(NewsPost.id == news_id).first()
        if not news:
            return 0, 0
        
        users = db.query(User).all()
        
        sent_count = 0
        failed_count = 0
        
        emoji = "🚨" if news.urgent else "📰"
        message = (
            f"{emoji} <b>{news.title}</b>\n\n"
            f"{news.content}"
        )
        
        for user in users:
            try:
                await bot.send_message(
                    user.telegram_id,
                    message,
                    parse_mode="HTML"
                )
                sent_count += 1
            except Exception as e:
                failed_count += 1
                print(f"Error sending to {user.telegram_id}: {e}")
        
        news.sent_to_all = True
        news.sent_count = sent_count
        db.commit()
        
        return sent_count, failed_count
    
    finally:
        db.close()


def get_recent_news(limit: int = 5) -> list:
    """Получить последние новости"""
    db = SessionLocal()
    try:
        news = db.query(NewsPost).order_by(
            NewsPost.created_at.desc()
        ).limit(limit).all()
        return news
    finally:
        db.close()


def get_urgent_news() -> list:
    """Получить срочные новости"""
    db = SessionLocal()
    try:
        news = db.query(NewsPost).filter(
            NewsPost.urgent == True
        ).order_by(NewsPost.created_at.desc()).all()
        return news
    finally:
        db.close()
