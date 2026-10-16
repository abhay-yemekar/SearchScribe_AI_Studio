"""Article endpoints: generation, listing, detail, rewrite, versions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from ...ai.styles import REWRITE_STYLES
from ...core.config import settings
from ...db.models import Article, User
from ...db.session import get_db
from ...schemas.article import (
    ArticleDetailOut,
    ArticleListOut,
    GenerateArticleRequest,
    RewriteRequest,
    RewriteStyleOut,
    RewriteStylesOut,
    SaveArticleRequest,
    UpdateArticleRequest,
    VersionDetailOut,
    VersionListOut,
)
from ...schemas.media import PhotoSearchOut, SavePhotosRequest
from ...services.article_service import ArticleService
from ...services.generation_service import GenerationService
from ...services.operation_service import OperationService
from ...services.photo_service import search_photos
from ..deps import get_current_user, user_rate_limit

router = APIRouter(prefix="/articles", tags=["articles"])


@router.post(
    "",
    response_model=ArticleDetailOut,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new article (article + SEO + HTML) from a query",
    dependencies=[user_rate_limit("generation", settings.rate_limit_generation_per_minute)],
)
def generate_article(
    payload: GenerateArticleRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ArticleDetailOut:
    article_id, key = OperationService(db).run(
        current_user.id, request_key, "generation", {"query": payload.query},
        lambda: GenerationService(db).generate_article(current_user, payload.query).article.id,
    )
    response.headers["X-Generation-Request"] = key
    return ArticleService(db).get_article(current_user, article_id)


@router.get(
    "",
    response_model=ArticleListOut,
    summary="List the current user's articles (newest first, cursor pagination)",
)
def list_articles(
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArticleListOut:
    return ArticleService(db).list_articles(current_user, limit=limit, cursor=cursor)


@router.get(
    "/rewrite-styles",
    response_model=RewriteStylesOut,
    summary="Available rewrite styles",
)
def rewrite_styles() -> RewriteStylesOut:
    return RewriteStylesOut(
        styles=[
            RewriteStyleOut(key=key, label=meta["label"]) for key, meta in REWRITE_STYLES.items()
        ]
    )


@router.get(
    "/{article_id}",
    response_model=ArticleDetailOut,
    summary="Get one article with markdown, SEO, and rendered HTML",
)
def get_article(
    article_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArticleDetailOut:
    return ArticleService(db).get_article(current_user, article_id)


@router.patch(
    "/{article_id}",
    response_model=ArticleDetailOut,
    summary="Rename an article",
)
def rename_article(
    article_id: int,
    payload: UpdateArticleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArticleDetailOut:
    return ArticleService(db).rename_article(current_user, article_id, payload.title)


@router.put(
    "/{article_id}/content",
    response_model=ArticleDetailOut,
    summary="Save article content and SEO as a new immutable version",
)
def save_article(
    article_id: int,
    payload: SaveArticleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArticleDetailOut:
    return ArticleService(db).save_article(current_user, article_id, payload)


@router.get(
    "/{article_id}/photos", response_model=PhotoSearchOut,
    summary="Search credited Commons photos for an owned article",
    dependencies=[user_rate_limit("photo-search", 10)],
)
def find_photos(
    article_id: int, query: str = Query(min_length=3, max_length=120),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
) -> PhotoSearchOut:
    _owned_article(db, current_user, article_id)
    from ...core.exceptions import BadRequestError

    if len(query.strip()) < 3:
        raise BadRequestError("Enter at least three characters to search.")
    return search_photos(query, current_user.id, article_id)


@router.put(
    "/{article_id}/photos", response_model=ArticleDetailOut,
    summary="Save selected photos and alt text as an immutable article version",
    dependencies=[user_rate_limit("photo-save", 20)],
)
def save_photos(
    article_id: int, payload: SavePhotosRequest,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
) -> ArticleDetailOut:
    return ArticleService(db).save_photos(current_user, article_id, payload)


@router.delete(
    "/{article_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an article and all its versions",
)
def delete_article(
    article_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    ArticleService(db).delete_article(current_user, article_id)


@router.post(
    "/{article_id}/duplicate",
    response_model=ArticleDetailOut,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate an article",
)
def duplicate_article(
    article_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArticleDetailOut:
    return ArticleService(db).duplicate_article(current_user, article_id)


@router.post(
    "/{article_id}/rewrite",
    response_model=ArticleDetailOut,
    summary="Rewrite the current article version in a given style",
    dependencies=[user_rate_limit("generation", settings.rate_limit_generation_per_minute)],
)
def rewrite_article(
    article_id: int,
    payload: RewriteRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ArticleDetailOut:
    article = _owned_article(db, current_user, article_id)
    from ...ai.styles import get_style

    try:
        get_style(payload.style)  # Reject invalid styles before reserving a daily slot.
    except ValueError as exc:
        from ...core.exceptions import BadRequestError

        raise BadRequestError("Unknown rewrite style.", code="UNKNOWN_STYLE") from exc

    def rewrite() -> int:
        GenerationService(db).rewrite_article(current_user, article, payload.style)
        return article_id

    result_id, key = OperationService(db).run(
        current_user.id, request_key, "rewrite", {"article_id": article_id, "style": payload.style},
        rewrite,
    )
    response.headers["X-Generation-Request"] = key
    return ArticleService(db).get_article(current_user, result_id)


@router.get(
    "/{article_id}/versions",
    response_model=VersionListOut,
    summary="List all versions of an article",
)
def list_versions(
    article_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VersionListOut:
    return ArticleService(db).list_versions(current_user, article_id)


@router.get(
    "/{article_id}/versions/{version}",
    response_model=VersionDetailOut,
    summary="Get one version's content",
)
def get_version(
    article_id: int,
    version: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VersionDetailOut:
    return ArticleService(db).get_version(current_user, article_id, version)


@router.post(
    "/{article_id}/versions/{version}/restore",
    response_model=ArticleDetailOut,
    summary="Restore an older version as the newest version",
)
def restore_version(
    article_id: int,
    version: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArticleDetailOut:
    ArticleService(db).restore_version(current_user, article_id, version)
    return ArticleService(db).get_article(current_user, article_id)


def _owned_article(db: Session, user: User, article_id: int) -> Article:
    from ...core.exceptions import NotFoundError
    from ...repositories.article_repo import ArticleRepository

    article = ArticleRepository(db).get_for_user(user.id, article_id)
    if article is None:
        raise NotFoundError("Article not found.")
    return article
