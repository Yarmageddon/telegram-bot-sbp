"""
Extended models v2 - новые модели для расширенного функционала
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from models import Base


class SubscriptionPlan(Base):
    """Тарифные планы"""
    __tablename__ = "subscription_plans"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    price = Column(Integer, nullable=False)  # в копейках
    duration_days = Column(Integer, nullable=False)
    features = Column(Text)  # JSON со списком возможностей
    level = Column(Integer, default=1)  # Уровень тарифа (для апгрейда/даунгрейда)
    active = Column(Boolean, default=True)


class Trial(Base):
    """Триал-периоды"""
    __tablename__ = "trials"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    started_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime, nullable=False)
    activated = Column(Boolean, default=False)
    converted_to_paid = Column(Boolean, default=False)


class Review(Base):
    """Отзывы и рейтинги"""
    __tablename__ = "reviews"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5
    text = Column(Text, nullable=True)
    suggestion = Column(Text, nullable=True)  # Предложение по улучшению
    category = Column(String(50), default="general")  # general, payment, support, feature
    created_at = Column(DateTime, default=datetime.now)
    admin_response = Column(Text, nullable=True)
    responded_at = Column(DateTime, nullable=True)


class NewsPost(Base):
    """Новости для push-уведомлений"""
    __tablename__ = "news_posts"
    
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    urgent = Column(Boolean, default=False)  # Срочная новость
    sent_to_all = Column(Boolean, default=False)
    sent_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    created_by = Column(Integer, ForeignKey("users.id"))


class Document(Base):
    """История конвертации документов"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    original_name = Column(String(255), nullable=False)
    original_format = Column(String(10), nullable=False)
    target_format = Column(String(10), nullable=False)
    file_path = Column(String(500), nullable=False)
    result_path = Column(String(500), nullable=True)
    status = Column(String(20), default="processing")  # processing, completed, failed
    created_at = Column(DateTime, default=datetime.now)


class DocumentTemplate(Base):
    """Шаблоны документов"""
    __tablename__ = "document_templates"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    template_path = Column(String(500), nullable=False)
    category = Column(String(50), default="general")
    variables = Column(Text)  # JSON со списком переменных
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class PersonalStats(Base):
    """Статистика пользователя для личного кабинета"""
    __tablename__ = "personal_stats"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    total_spent = Column(Integer, default=0)  # в копейках
    documents_converted = Column(Integer, default=0)
    ocr_processed = Column(Integer, default=0)
    reviews_given = Column(Integer, default=0)
    referrals_count = Column(Integer, default=0)
    last_activity = Column(DateTime, default=datetime.now)
