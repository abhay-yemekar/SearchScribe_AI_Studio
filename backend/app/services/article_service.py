"""Article management: retrieval, rendering, rename, delete, duplicate, versions."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from ..ai.renderer import render_article_html
from ..ai.sanitizer import sanitize_document
from ..ai.schemas import GeneratedArticle, SeoResult
from ..core.exceptions import NotFoundError
from ..db.models import Article, User
from ..repositories.article_repo import ArticleRepository
from ..schemas.article import (
    ArticleDetailOut,
    ArticleListItem,
    ArticleListOut,
    SeoOut,
    VersionDetailOut,
    VersionListItem,
    VersionListOut,
)

logger = logging.getLogger(__name__)


class ArticleService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.articles = ArticleRepository(db)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _require_article(self, user: User, article_id: int) -> Article:
        article = self.articles.get_for_user(user.id, article_id)
        if article is None:
            raise NotFoundError("Article not found.")
        return article

    def _current_content(self, article: Article) -> GeneratedArticle:
        latest = self.articles.latest_version(article.id)
        if latest is None:
            # Creation always writes version 1; reaching here means data loss.
            raise NotFoundError("Article content is missing.")
        return GeneratedArticle.model_validate_json(latest.content)

    def _detail(self, article: Article) -> ArticleDetailOut:
        content = self._current_content(article)
        latest = self.articles.latest_version(article.id)
        seo_row = self.articles.get_seo(article.id)
        seo_out: SeoOut | None = None
        seo_model = None
        if seo_row is not None:
            seo_out = SeoOut(
                title=seo_row.title,
                description=seo_row.description,
                keywords=seo_row.keywords,
                og_title=seo_row.og_title,
                og_description=seo_row.og_description,
                canonical_url=seo_row.canonical_url,
                robots=seo_row.robots,
            )
            seo_model = SeoResult(
                title=seo_row.title,
                description=seo_row.description,
                keywords=seo_row.keywords,
                og_title=seo_row.og_title,
                og_description=seo_row.og_description,
            )
        html = sanitize_document(render_article_html(content, seo_model))
        return ArticleDetailOut(
            id=article.id,
            title=article.title,
            query=article.query,
            status=article.status,
            current_version=latest.version if latest else 0,
            markdown=content.to_markdown(),
            html=html,
            seo=seo_out,
            created_at=article.created_at,
            updated_at=article.updated_at,
        )

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------
    def get_article(self, user: User, article_id: int) -> ArticleDetailOut:
        return self._detail(self._require_article(user, article_id))

    def list_articles(
        self, user: User, *, limit: int, cursor: str | None
    ) -> ArticleListOut:
        cursor_id = int(cursor) if cursor else None
        rows = self.articles.list_for_user(user.id, limit=limit, cursor=cursor_id)
        items = []
        for row in rows:
            latest = self.articles.latest_version(row.id)
            items.append(
                ArticleListItem(
                    id=row.id,
                    title=row.title,
                    query=row.query,
                    status=row.status,
                    current_version=latest.version if latest else 0,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
            )
        next_cursor = str(rows[-1].id) if len(rows) == limit else None
        return ArticleListOut(items=items, next_cursor=next_cursor)

    def list_versions(self, user: User, article_id: int) -> VersionListOut:
        article = self._require_article(user, article_id)
        versions = self.articles.versions_for_article(article.id)
        items = [
            VersionListItem(
                version=v.version,
                change_type=v.change_type,
                word_count=len(
                    GeneratedArticle.model_validate_json(v.content)
                    .to_markdown()
                    .split()
                ),
                created_at=v.created_at,
            )
            for v in versions
        ]
        return VersionListOut(items=items)

    def get_version(self, user: User, article_id: int, version: int) -> VersionDetailOut:
        article = self._require_article(user, article_id)
        record = self.articles.get_version(article.id, version)
        if record is None:
            raise NotFoundError("Version not found.")
        content = GeneratedArticle.model_validate_json(record.content)
        return VersionDetailOut(
            version=record.version,
            change_type=record.change_type,
            markdown=content.to_markdown(),
            created_at=record.created_at,
        )

    # ------------------------------------------------------------------
    # mutations
    # ------------------------------------------------------------------
    def rename_article(self, user: User, article_id: int, title: str) -> ArticleDetailOut:
        article = self._require_article(user, article_id)
        self.articles.rename(article, title.strip())
        logger.info("article.renamed", extra={"user_id": user.id, "article_id": article_id})
        return self._detail(article)

    def delete_article(self, user: User, article_id: int) -> None:
        if not self.articles.delete_for_user(user.id, article_id):
            raise NotFoundError("Article not found.")
        logger.info("article.deleted", extra={"user_id": user.id, "article_id": article_id})

    def duplicate_article(self, user: User, article_id: int) -> ArticleDetailOut:
        article = self._require_article(user, article_id)
        latest = self.articles.latest_version(article.id)
        seo_row = self.articles.get_seo(article.id)

        copy = self.articles.create(
            user_id=user.id,
            title=article.title[:190] + " (copy)",
            query=article.query,
        )
        if latest is not None:
            self.articles.add_version(
                copy, version=1, content=latest.content, change_type="generation"
            )
        if seo_row is not None:
            self.articles.set_seo(
                copy,
                {
                    "title": seo_row.title,
                    "description": seo_row.description,
                    "keywords": seo_row.keywords,
                    "og_title": seo_row.og_title,
                    "og_description": seo_row.og_description,
                },
            )
        self.db.commit()
        logger.info(
            "article.duplicated",
            extra={"user_id": user.id, "article_id": article_id, "copy_id": copy.id},
        )
        return self._detail(copy)

    def restore_version(self, user: User, article_id: int, version: int) -> dict:
        article = self._require_article(user, article_id)
        record = self.articles.get_version(article.id, version)
        if record is None:
            raise NotFoundError("Version not found.")
        latest = self.articles.latest_version(article.id)
        next_version = (latest.version if latest else 0) + 1
        self.articles.add_version(
            article,
            version=next_version,
            content=record.content,
            change_type="restore",
        )
        self.db.commit()
        content = GeneratedArticle.model_validate_json(record.content)
        logger.info(
            "article.version_restored",
            extra={"user_id": user.id, "article_id": article_id, "version": version},
        )
        return {
            "version": next_version,
            "markdown": content.to_markdown(),
            "restored_from": version,
        }
