"""
database.py — подключение к БД и инициализация.
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

# ─── Приводим URL к формату, который SQLAlchemy понимает однозначно ──
# Railway может отдать postgres:// (короткий) — меняем на postgresql+psycopg2://
# (явно указываем драйвер psycopg2, чтобы SQLAlchemy не пытался искать psycopg3)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://", "postgresql+psycopg2://", 1
    )
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://", "postgresql+psycopg2://", 1
    )

logger.info(f"🗄 БД URL: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")


if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    logger.info("🗄 БД: SQLite")
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=10,
    )
    logger.info("🗄 БД: PostgreSQL (psycopg2)")


# ═══════════════════════════════════════════════════════════════
# СЕССИИ
# ═══════════════════════════════════════════════════════════════

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_session():
    return SessionLocal()


# ═══════════════════════════════════════════════════════════════
# ИНИЦИАЛИЗАЦИЯ ТАБЛИЦ
# ═══════════════════════════════════════════════════════════════

async def init_db() -> None:
    """Создать все таблицы, если их нет."""
    from models import Plant, Reminder  # noqa: F401
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Таблицы созданы/проверены")
