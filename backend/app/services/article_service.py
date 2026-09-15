"""Article management: retrieval, rendering, rename, delete, duplicate, versions."""

from __future__ import annotations

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..ai.renderer import render_article_html
from ..ai.sanitizer import sanitize_document
from ..ai.schemas import GeneratedArticle, SeoResult
from ..core.exceptions import BadRequestError, ConflictError, NotFoundError
from ..db.models import Article, User
from ..repositories.article_repo import ArticleRepository
from ..schemas.article import (
    ArticleDetailOut,
    ArticleListItem,
    ArticleListOut,
    SaveArticleRequest,
    SeoOut,
    VersionDetailOut,
    VersionListItem,
    VersionListOut,
)

logger = logging.getLogger(__name__)


def _seo_values(seo: SeoResult) -> dict[str, object]:
    return seo.model_dump()


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
        latest = self.articles.latest_version(article.id)
        if latest is None:
            raise NotFoundError("Article content is missing.")
        content = GeneratedArticle.model_validate_json(latest.content)
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
                robots=seo_row.robots,
                canonical_url=seo_row.canonical_url,
            )
        html = sanitize_document(render_article_html(content, seo_model))
        return ArticleDetailOut(
            id=article.id,
            title=article.title,
            query=article.query,
            status=article.status,
            current_version=latest.version if latest else 0,
            content=content,
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

    def list_articles(self, user: User, *, limit: int, cursor: str | None) -> ArticleListOut:
        if cursor is not None and (
            not cursor.isascii() or not cursor.isdecimal() or len(cursor) > 18 or int(cursor) < 1
        ):
            raise BadRequestError("Invalid article cursor.", code="INVALID_CURSOR")
        cursor_id = int(cursor) if cursor else None
        fetched = self.articles.list_for_user(user.id, limit=limit + 1, cursor=cursor_id)
        rows = fetched[:limit]
        latest_by_id = self.articles.latest_versions([row.id for row in rows])
        items = []
        for row in rows:
            latest = latest_by_id.get(row.id)
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
        next_cursor = str(rows[-1].id) if len(fetched) > limit else None
        return ArticleListOut(items=items, next_cursor=next_cursor)

    def list_versions(self, user: User, article_id: int) -> VersionListOut:
        article = self._require_article(user, article_id)
        versions = self.articles.versions_for_article(article.id)
        items = [
            VersionListItem(
                version=v.version,
                change_type=v.change_type,
                word_count=len(
                    GeneratedArticle.model_validate_json(v.content).to_markdown().split()
                ),
                complete_snapshot=v.seo_snapshot is not None,
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

        if latest is None:
            raise NotFoundError("Article content is missing.")

        copy = self.articles.create(
            user_id=user.id,
            title=article.title[:190] + " (copy)",
            query=article.query,
        )
        if latest is not None:
            self.articles.add_version(
                copy,
                version=1,
                content=latest.content,
                change_type="generation",
                seo_snapshot=latest.seo_snapshot,
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
                    "robots": seo_row.robots,
                    "canonical_url": seo_row.canonical_url,
                },
            )
        self.db.commit()
        logger.info(
            "article.duplicated",
            extra={"user_id": user.id, "article_id": article_id, "copy_id": copy.id},
        )
        return self._detail(copy)

    def save_article(
        self, user: User, article_id: int, payload: SaveArticleRequest
    ) -> ArticleDetailOut:
        article = self._require_article(user, article_id)
        latest = self.articles.latest_version(article.id)
        if latest is None:
            raise NotFoundError("Article content is missing.")
        if latest.version != payload.base_version:
            raise ConflictError(
                "This article changed after you opened it. Reload before saving.",
                code="STALE_ARTICLE_VERSION",
                details={"current_version": latest.version},
            )

        seo = SeoResult.model_validate(payload.seo.model_dump())
        next_version = latest.version + 1
        self.articles.add_version(
            article,
            version=next_version,
            content=payload.content.model_dump_json(),
            change_type="edit",
            seo_snapshot=seo.model_dump_json(),
        )
        article.title = payload.content.title
        self.articles.set_seo(article, _seo_values(seo))
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            current = self.articles.latest_version(article.id)
            raise ConflictError(
                "This article changed while it was being saved. Reload before saving.",
                code="STALE_ARTICLE_VERSION",
                details={"current_version": current.version if current else None},
            ) from exc
        logger.info(
            "article.edited",
            extra={"user_id": user.id, "article_id": article.id, "version": next_version},
        )
        return self._detail(article)

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
            seo_snapshot=record.seo_snapshot,
        )
        content = GeneratedArticle.model_validate_json(record.content)
        article.title = content.title
        if record.seo_snapshot is not None:
            restored_seo = SeoResult.model_validate_json(record.seo_snapshot)
            self.articles.set_seo(article, _seo_values(restored_seo))
        self.db.commit()
        logger.info(
            "article.version_restored",
            extra={"user_id": user.id, "article_id": article_id, "version": version},
        )
        return {
            "version": next_version,
            "markdown": content.to_markdown(),
            "restored_from": version,
        }
