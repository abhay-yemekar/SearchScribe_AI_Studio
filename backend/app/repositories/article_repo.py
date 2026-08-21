"""Data access for articles, versions, and SEO metadata. Always user-scoped."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..db.models import Article, ArticleVersion, SeoMetadata

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50


class ArticleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- reads ---

    def get_for_user(self, user_id: int, article_id: int) -> Article | None:
        return self.db.scalar(
            select(Article).where(
                Article.id == article_id, Article.user_id == user_id
            )
        )

    def list_for_user(
        self, user_id: int, *, limit: int, cursor: int | None
    ) -> list[Article]:
        """Newest-first cursor pagination (cursor = last seen article id)."""
        query = (
            select(Article)
            .where(Article.user_id == user_id)
            .order_by(Article.id.desc())
            .limit(min(limit, MAX_PAGE_SIZE))
        )
        if cursor is not None:
            query = query.where(Article.id < cursor)
        return list(self.db.scalars(query))

    def latest_version(self, article_id: int) -> ArticleVersion | None:
        return self.db.scalar(
            select(ArticleVersion)
            .where(ArticleVersion.article_id == article_id)
            .order_by(ArticleVersion.version.desc())
            .limit(1)
        )

    def get_version(self, article_id: int, version: int) -> ArticleVersion | None:
        return self.db.scalar(
            select(ArticleVersion).where(
                ArticleVersion.article_id == article_id,
                ArticleVersion.version == version,
            )
        )

    def versions_for_article(self, article_id: int) -> list[ArticleVersion]:
        return list(
            self.db.scalars(
                select(ArticleVersion)
                .where(ArticleVersion.article_id == article_id)
                .order_by(ArticleVersion.version.desc())
            )
        )

    def get_seo(self, article_id: int) -> SeoMetadata | None:
        return self.db.scalar(
            select(SeoMetadata).where(SeoMetadata.article_id == article_id)
        )

    def count_for_user(self, user_id: int) -> int:
        return int(
            self.db.scalar(
                select(func.count()).select_from(Article).where(
                    Article.user_id == user_id
                )
            )
            or 0
        )

    # --- writes ---

    def create(
        self, *, user_id: int, title: str, query: str, status: str = "ready"
    ) -> Article:
        article = Article(user_id=user_id, title=title, query=query, status=status)
        self.db.add(article)
        self.db.commit()
        return article

    def add_version(
        self,
        article: Article,
        *,
        version: int,
        content: str,
        change_type: str,
    ) -> ArticleVersion:
        record = ArticleVersion(
            article_id=article.id,
            version=version,
            content=content,
            change_type=change_type,
        )
        self.db.add(record)
        self.db.flush()
        return record

    def set_seo(self, article: Article, seo_values: dict) -> SeoMetadata:
        """Insert or replace the 1:1 SEO row for an article."""
        existing = self.get_seo(article.id)
        if existing is not None:
            self.db.delete(existing)
            self.db.flush()
        row = SeoMetadata(article_id=article.id, **seo_values)
        self.db.add(row)
        self.db.flush()
        return row

    def rename(self, article: Article, title: str) -> Article:
        article.title = title
        self.db.commit()
        return article

    def delete_for_user(self, user_id: int, article_id: int) -> bool:
        result = self.db.execute(
            delete(Article).where(Article.id == article_id, Article.user_id == user_id)
        )
        self.db.commit()
        return result.rowcount > 0
