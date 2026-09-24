"""
Модели для расширенных функций
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from models import Base


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    duration_days = Column(Integer, nullable=False)
    features = Column(Text, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class Trial(Base):
    __tablename__ = "trials"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    started_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)


class Review(Base):
    __tablename__ = "reviews"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    rating = Column(Integer, nullable=False)
    text = Column(Text, nullable=True)
    category = Column(String, nullable=True)
    suggestion = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class NewsPost(Base):
    __tablename__ = "news_posts"
    
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    urgent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    author_id = Column(Integer, nullable=False)


class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class DocumentTemplate(Base):
    __tablename__ = "document_templates"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    template_data = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class PersonalStats(Base):
    __tablename__ = "personal_stats"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    documents_converted = Column(Integer, default=0)
    ocr_processed = Column(Integer, default=0)
    reviews_given = Column(Integer, default=0)
    referrals_count = Column(Integer, default=0)
    last_activity = Column(DateTime, default=datetime.now)
