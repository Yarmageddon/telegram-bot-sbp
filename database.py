"""
database.py — подключение к БД и инициализация.

ВАЖНО: этот файл НЕ должен импортировать из самого себя!
Только:
- стандартные модули (os, logging)
- sqlalchemy
- models (для Base)
"""

import os
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# ПОДКЛЮЧЕНИЕ К БД
# ═══════════════════════════════════════════════════════════════

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bot.db")

# Railway отдаёт postgres://, SQLAlchemy хочет postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    logger.info(f"🗄 БД: SQLite ({DATABASE_URL})")
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=10,
    )
    logger.info("🗄 БД: PostgreSQL")


# ═══════════════════════════════════════════════════════════════
# СЕССИИ
# ═══════════════════════════════════════════════════════════════

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_session():
    """Получить сессию. Использовать в `with SessionLocal() as db:`."""
    return SessionLocal()


# ═══════════════════════════════════════════════════════════════
# ИНИЦИАЛИЗАЦИЯ ТАБЛИЦ
# ═══════════════════════════════════════════════════════════════

async def init_db() -> None:
    """Создать все таблицы, если их нет."""
    # Импортируем модели, чтобы Base «увидел» их перед create_all
    from models import Plant, Reminder  # noqa: F401
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Таблицы созданы/проверены")
