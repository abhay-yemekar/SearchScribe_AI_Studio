"""Article endpoints: generation, listing, detail, rewrite, versions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from ...ai.styles import REWRITE_STYLES
from ...core.config import settings
from ...core.rate_limit import rate_limit
from ...db.models import User
from ...db.session import get_db
from ...schemas.article import (
    ArticleDetailOut,
    ArticleListOut,
    GenerateArticleRequest,
    RewriteRequest,
    RewriteStyleOut,
    RewriteStylesOut,
    UpdateArticleRequest,
    VersionDetailOut,
    VersionListOut,
)
from ...services.article_service import ArticleService
from ...services.generation_service import GenerationService
from ..deps import get_current_user

router = APIRouter(prefix="/articles", tags=["articles"])


@router.post(
    "",
    response_model=ArticleDetailOut,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new article (article + SEO + HTML) from a query",
    dependencies=[rate_limit("generation", settings.rate_limit_generation_per_minute)],
)
def generate_article(
    payload: GenerateArticleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    outcome = GenerationService(db).generate_article(current_user, payload.query)
    return ArticleService(db).get_article(current_user, outcome.article.id)


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
):
    return ArticleService(db).list_articles(current_user, limit=limit, cursor=cursor)


@router.get(
    "/rewrite-styles",
    response_model=RewriteStylesOut,
    summary="Available rewrite styles",
)
def rewrite_styles():
    return RewriteStylesOut(
        styles=[
            RewriteStyleOut(key=key, label=meta["label"])
            for key, meta in REWRITE_STYLES.items()
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
):
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
):
    return ArticleService(db).rename_article(current_user, article_id, payload.title)


@router.delete(
    "/{article_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an article and all its versions",
)
def delete_article(
    article_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
):
    return ArticleService(db).duplicate_article(current_user, article_id)


@router.post(
    "/{article_id}/rewrite",
    response_model=ArticleDetailOut,
    summary="Rewrite the current article version in a given style",
    dependencies=[rate_limit("generation", settings.rate_limit_generation_per_minute)],
)
def rewrite_article(
    article_id: int,
    payload: RewriteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    article = _owned_article(db, current_user, article_id)
    GenerationService(db).rewrite_article(current_user, article, payload.style)
    return ArticleService(db).get_article(current_user, article_id)


@router.get(
    "/{article_id}/versions",
    response_model=VersionListOut,
    summary="List all versions of an article",
)
def list_versions(
    article_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
):
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
):
    ArticleService(db).restore_version(current_user, article_id, version)
    return ArticleService(db).get_article(current_user, article_id)


def _owned_article(db: Session, user: User, article_id: int):
    from ...core.exceptions import NotFoundError
    from ...repositories.article_repo import ArticleRepository

    article = ArticleRepository(db).get_for_user(user.id, article_id)
    if article is None:
        raise NotFoundError("Article not found.")
    return article
