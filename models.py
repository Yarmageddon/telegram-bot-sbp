"""
models.py — модели БД и подключение.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ─── Берём URL из переменных окружения ──────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bot.db")

# Railway отдаёт postgres://, SQLAlchemy ждёт postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# ─── Создаём engine ─────────────────────────────────────────────
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    # PostgreSQL — пул соединений для стабильности на Railway
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,   # проверять соединение перед использованием
        pool_recycle=300,      # пересоздавать соединения каждые 5 мин
    )

# ─── Сессии ─────────────────────────────────────────────────────
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ─── Базовый класс моделей ──────────────────────────────────────
Base = declarative_base()


# ─── Инициализация таблиц ───────────────────────────────────────
async def init_db() -> None:
    """Создать все таблицы (если их нет)."""
    # Импорт моделей — обязателен, чтобы Base «увидел» их
    # Если у вас уже импортируются ниже — оставьте только Base.metadata.create_all.
    Base.metadata.create_all(bind=engine)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(64), nullable=True)
    first_name = Column(String(64), nullable=True)
    last_name = Column(String(64), nullable=True)
    referral_code = Column(String(32), unique=True, nullable=True)
    referred_by = Column(Integer, nullable=True)       # user.id того, кто пригласил
    referral_bonus_given = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    is_banned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    last_seen = Column(DateTime, default=datetime.now)


class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    plan = Column(String(32), nullable=False)           # basic / pro / business
    starts_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime, nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(8), default="RUB")
    plan = Column(String(32), nullable=True)
    status = Column(String(16), default="pending")     # pending / completed / failed
    payment_method = Column(String(32), default="manual")
    created_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime, nullable=True)


class Trial(Base):
    __tablename__ = "trials"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, unique=True, index=True)
    started_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=True)


class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    rating = Column(Integer, nullable=False)           # 1-5
    text = Column(Text, nullable=True)
    category = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class SupportTicket(Base):
    __tablename__ = "support_tickets"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    message = Column(Text, nullable=False)
    admin_response = Column(Text, nullable=True)
    status = Column(String(16), default="open")        # open / answered / closed
    created_at = Column(DateTime, default=datetime.now)
    answered_at = Column(DateTime, nullable=True)


class NewsPost(Base):
    __tablename__ = "news_posts"
    id = Column(Integer, primary_key=True)
    title = Column(String(256), nullable=False)
    content = Column(Text, nullable=False)
    urgent = Column(Boolean, default=False)
    author_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


def init_db():
    Base.metadata.create_all(bind=engine)
