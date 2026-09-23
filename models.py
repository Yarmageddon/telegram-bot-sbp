from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func
from datetime import datetime
from config import settings

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))
    created_at = Column(DateTime, default=datetime.now)
    
    subscriptions = relationship("Subscription", back_populates="user")
    payments = relationship("Payment", back_populates="user")


class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan = Column(String(50), nullable=False)
    started_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime, nullable=False)
    active = Column(Boolean, default=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    
    user = relationship("User", back_populates="subscriptions")
    payment = relationship("Payment", back_populates="subscription")
    
    @property
    def is_active(self) -> bool:
        return self.active and datetime.now() < self.expires_at


class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider_transaction_id = Column(String(255), unique=True, nullable=False)
    amount = Column(Integer, nullable=False)
    currency = Column(String(10), nullable=False)
    status = Column(String(50), nullable=False)
    payload = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    
    user = relationship("User", back_populates="payments")
    subscription = relationship("Subscription", back_populates="payment", uselist=False)


# Database setup
engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    print("✅ Database initialized")


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
