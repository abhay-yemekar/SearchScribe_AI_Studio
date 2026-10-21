"""Article management: retrieval, rendering, rename, delete, duplicate, versions."""

from __future__ import annotations

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..ai.renderer import render_article_html
from ..ai.sanitizer import sanitize_document
from ..ai.schemas import SeoResult, SeoReviewStatus
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
from ..schemas.media import ArticleDocument, ArticlePhoto, SavePhotosRequest
from .photo_service import selected_photo

logger = logging.getLogger(__name__)


def _seo_values(seo: SeoResult) -> dict[str, object]:
    # Quality lives in version snapshots, not the SEO ORM table.
    return seo.model_dump(exclude={"review_status"})


def _snapshot_status(snapshot: str | None) -> SeoReviewStatus:
    return SeoResult.model_validate_json(snapshot).review_status if snapshot else "unknown"


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

    def _stale(self, current_version: int, action: str) -> ConflictError:
        return ConflictError(
            f"This article changed after you opened it. Reload before {action}.",
            code="STALE_ARTICLE_VERSION",
            details={"current_version": current_version},
        )

    def _lost_race(self, article: Article, action: str) -> ConflictError:
        """Another request wrote the same version number first (unique constraint)."""
        self.db.rollback()
        current = self.articles.latest_version(article.id)
        return ConflictError(
            f"This article changed while it was being {action}. Reload and try again.",
            code="STALE_ARTICLE_VERSION",
            details={"current_version": current.version if current else None},
        )

    def _current_content(self, article: Article) -> ArticleDocument:
        latest = self.articles.latest_version(article.id)
        if latest is None:
            # Creation always writes version 1; reaching here means data loss.
            raise NotFoundError("Article content is missing.")
        return ArticleDocument.model_validate_json(latest.content)

    def _detail(self, article: Article) -> ArticleDetailOut:
        latest = self.articles.latest_version(article.id)
        if latest is None:
            raise NotFoundError("Article content is missing.")
        content = ArticleDocument.model_validate_json(latest.content)
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
                review_status=_snapshot_status(latest.seo_snapshot),
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
        html = sanitize_document(render_article_html(content, seo_model, photos=content.photos))
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
                word_count=ArticleDocument.model_validate_json(v.content).word_count,
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
        content = ArticleDocument.model_validate_json(record.content)
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
            raise self._stale(latest.version, "saving")

        seo = SeoResult.model_validate(payload.seo.model_dump())
        current_content = ArticleDocument.model_validate_json(latest.content)
        current_seo = self.articles.get_seo(article.id)
        current_values = {
            field: getattr(current_seo, field) for field in _seo_values(seo)
        } if current_seo is not None else None
        seo_changed = _seo_values(seo) != current_values
        # Source provenance is server-owned. An edit keeps its original source
        # snapshot; it cannot manufacture a research badge or replace citations.
        payload.content.research = current_content.research
        # Legacy clients omit photos, and ordinary text edits cannot forge credits.
        section_ids = {section.id for section in payload.content.sections}
        edited = ArticleDocument(**payload.content.model_dump(), photos=[
            photo for photo in current_content.photos
            if photo.section_id is None or photo.section_id in section_ids
        ])
        content_changed = edited.model_dump() != current_content.model_dump()
        # SeoInput ignores client quality fields. Only real editor changes alter
        # status; article edits make retained metadata stale until reviewed.
        seo.review_status = (
            "edited" if seo_changed else "needs_review" if content_changed
            else _snapshot_status(latest.seo_snapshot)
        )
        next_version = latest.version + 1
        # add_version flushes, so a concurrent save fails here, not at commit.
        try:
            article.title = payload.content.title
            self.articles.add_version(
                article,
                version=next_version,
                content=edited.model_dump_json(),
                change_type="edit",
                seo_snapshot=seo.model_dump_json(),
            )
            self.articles.set_seo(article, _seo_values(seo))
            self.db.commit()
        except IntegrityError as exc:
            raise self._lost_race(article, "saved") from exc
        logger.info(
            "article.edited",
            extra={"user_id": user.id, "article_id": article.id, "version": next_version},
        )
        return self._detail(article)

    def save_photos(
        self, user: User, article_id: int, payload: SavePhotosRequest,
    ) -> ArticleDetailOut:
        article = self._require_article(user, article_id)
        latest = self.articles.latest_version(article.id)
        if latest is None:
            raise NotFoundError("Article content is missing.")
        if latest.version != payload.base_version:
            raise ConflictError("This article changed. Reload before saving photos.",
                                code="STALE_ARTICLE_VERSION")
        document = ArticleDocument.model_validate_json(latest.content)
        existing = {photo.id: photo for photo in document.photos}
        photos: list[ArticlePhoto] = []
        slots: set[str | None] = set()
        ids: set[str] = set()
        sections = {section.id for section in document.sections}
        for choice in payload.photos:
            if choice.section_id in slots or (
                choice.section_id is not None and choice.section_id not in sections
            ):
                raise BadRequestError("Choose one photo per existing section or cover.",
                                      code="INVALID_PHOTO_POSITION")
            slots.add(choice.section_id)
            if choice.id:
                original = existing.get(choice.id)
                if original is None or choice.id in ids:
                    raise BadRequestError("That photo is no longer in this article.",
                                          code="INVALID_PHOTO_SELECTION")
                photo = ArticlePhoto.model_validate({**original.model_dump(),
                    "alt": choice.alt, "section_id": choice.section_id})
            else:
                asset = selected_photo(choice.selection_token or "", user.id, article.id)
                photo = ArticlePhoto(
                    **asset.model_dump(), alt=choice.alt, section_id=choice.section_id,
                )
            ids.add(photo.id)
            photos.append(photo)
        document.photos = photos
        document = ArticleDocument.model_validate(document.model_dump())
        try:
            self.articles.add_version(article, version=latest.version + 1,
                content=document.model_dump_json(), change_type="photos",
                seo_snapshot=latest.seo_snapshot)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("This article changed while saving. Reload before saving photos.",
                                code="STALE_ARTICLE_VERSION") from exc
        return self._detail(article)

    def restore_version(
        self, user: User, article_id: int, version: int, base_version: int | None = None
    ) -> dict:
        """Copy an old version forward. `base_version` is optional for older clients."""
        article = self._require_article(user, article_id)
        record = self.articles.get_version(article.id, version)
        if record is None:
            raise NotFoundError("Version not found.")
        latest = self.articles.latest_version(article.id)
        current_version = latest.version if latest else 0
        if base_version is not None and base_version != current_version:
            raise self._stale(current_version, "restoring")
        next_version = current_version + 1
        content = ArticleDocument.model_validate_json(record.content)
        try:
            article.title = content.title
            self.articles.add_version(
                article,
                version=next_version,
                content=record.content,
                change_type="restore",
                seo_snapshot=record.seo_snapshot,
            )
            if record.seo_snapshot is not None:
                restored_seo = SeoResult.model_validate_json(record.seo_snapshot)
                self.articles.set_seo(article, _seo_values(restored_seo))
            self.db.commit()
        except IntegrityError as exc:
            raise self._lost_race(article, "restored") from exc
        logger.info(
            "article.version_restored",
            extra={"user_id": user.id, "article_id": article_id, "version": version},
        )
        return {
            "version": next_version,
            "markdown": content.to_markdown(),
            "restored_from": version,
        }
