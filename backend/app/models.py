# backend/app/models.py
from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ArticleHistory(Base):
    """
    Simple history table – lets you later extend the UI with
    'previous generations' if you want.
    """

    __tablename__ = "article_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    query = Column(String, index=True)
    article = Column(Text)         # HTML article body
    seo_metadata = Column(Text)    # JSON string
    html = Column(Text)            # full HTML page
    created_at = Column(DateTime, default=datetime.utcnow)
