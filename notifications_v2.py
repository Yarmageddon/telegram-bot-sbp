"""
Расширенная система уведомлений и новостей
"""
from datetime import datetime
from models import SessionLocal, User
from models_v2 import NewsPost


def create_news(title: str, content: str, urgent: bool = False, author_id: int = 0) -> dict:
    """Создать новостную запись"""
    db = SessionLocal()
    try:
        news = NewsPost(
            title=title,
            content=content,
            urgent=urgent,
            author_id=author_id
        )
        db.add(news)
        db.commit()
        return {"success": True, "news_id": news.id}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def broadcast_news(bot, news_id: int) -> tuple:
    """Рассылка новости всем пользователям"""
    db = SessionLocal()
    try:
        news = db.query(NewsPost).filter(NewsPost.id == news_id).first()
        if not news:
            return 0, 0
        
        users = db.query(User).filter(User.is_active == True).all()
        
        sent = 0
        failed = 0
        
        text = f"{'🚨' if news.urgent else '📰'} <b>{news.title}</b>\n\n{news.content}"
        
        for user in users:
            try:
                await bot.send_message(user.telegram_id, text, parse_mode="HTML")
                sent += 1
            except Exception as e:
                failed += 1
                print(f"Ошибка отправки пользователю {user.telegram_id}: {e}")
        
        return sent, failed
    finally:
        db.close()
