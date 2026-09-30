"""
database.py — подключение к БД и инициализация.
"""

import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bot.db")

# Railway отдаёт postgres://, SQLAlchemy хочет postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=10,
    )

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


async def init_db() -> None:
    """Создать все таблицы, если их нет."""
    # Импортируем модели, чтобы Base «увидел» их перед create_all
    from models import Plant, Reminder  # noqa: F401
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Таблицы созданы/проверены")


def get_session():
    """Получить сессию. Использовать в `with SessionLocal() as db:`."""
    return SessionLocal()
