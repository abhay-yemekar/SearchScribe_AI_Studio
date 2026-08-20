"""Article, article version, and SEO metadata models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, TimestampMixin, utc_now

# JSONB on PostgreSQL, plain JSON elsewhere (SQLite dev/test).
KeywordsJSON = JSON().with_variant(JSONB(), "postgresql")


class Article(TimestampMixin, Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="Untitled")
    query: Mapped[str] = mapped_column(String(500), nullable=False)
    # ready | failed (reserved for future background generation)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ready")

    versions: Mapped[list[ArticleVersion]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        order_by="ArticleVersion.version.desc()",
    )
    seo: Mapped[SeoMetadata | None] = relationship(
        back_populates="article", cascade="all, delete-orphan", uselist=False
    )


class ArticleVersion(Base):
    """Immutable snapshot of article content. Version numbers start at 1."""

    __tablename__ = "article_versions"
    __table_args__ = (UniqueConstraint("article_id", "version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # generation | rewrite | restore | edit
    change_type: Mapped[str] = mapped_column(String(30), nullable=False, default="generation")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    article: Mapped[Article] = relationship(back_populates="versions")


class SeoMetadata(TimestampMixin, Base):
    """1:1 SEO metadata attached to an article."""

    __tablename__ = "seo_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(400), nullable=False)
    keywords: Mapped[list[str]] = mapped_column(KeywordsJSON, nullable=False, default=list)
    og_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    og_description: Mapped[str | None] = mapped_column(String(400), nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    robots: Mapped[str] = mapped_column(String(50), nullable=False, default="index, follow")

    article: Mapped[Article] = relationship(back_populates="seo")
