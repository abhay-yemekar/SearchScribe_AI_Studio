"""Generation pipeline: query -> structured article -> SEO -> safe HTML -> persistence.

Failure policy: provider failures NEVER produce fake content. A failed article
generation records a failed Generation row and raises ExternalServiceError.
A failed SEO generation degrades to deterministic fallback metadata (status
"partial" semantics live in the Generation rows, not the article).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..ai.base import LLMError, LLMProvider, call_with_retry
from ..ai.factory import get_provider
from ..ai.renderer import _fallback_seo, render_article_html
from ..ai.sanitizer import sanitize_document
from ..ai.schemas import GeneratedArticle, SeoResult
from ..ai.styles import get_style
from ..ai.validation import normalize_seo
from ..core.config import settings
from ..core.exceptions import BadRequestError, ExternalServiceError
from ..db.models import Article, User
from ..repositories.article_repo import ArticleRepository
from ..repositories.generation_repo import GenerationRepository

logger = logging.getLogger(__name__)


@dataclass
class GenerationOutcome:
    article: Article
    markdown: str
    html: str
    seo: SeoResult
    seo_fallback_used: bool


class GenerationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.articles = ArticleRepository(db)
        self.generations = GenerationRepository(db)

    # ------------------------------------------------------------------
    # article + SEO generation
    # ------------------------------------------------------------------
    def generate_article(self, user: User, query: str) -> GenerationOutcome:
        query = query.strip()
        if not query:
            raise BadRequestError("Query cannot be empty.")
        if len(query) > settings.max_query_length:
            raise BadRequestError(
                f"Query too long (max {settings.max_query_length} characters).",
                code="QUERY_TOO_LONG",
            )

        try:
            provider = get_provider()
        except ValueError as exc:
            # Misconfigured provider (e.g. gemini without an API key).
            logger.error("generation.provider_unavailable", extra={"user_id": user.id})
            raise ExternalServiceError(
                "Content generation is not configured on this server.",
                code="AI_PROVIDER_UNAVAILABLE",
            ) from exc

        # --- article ---
        try:
            article_response = call_with_retry(
                lambda: provider.generate(
                    "article_generation",
                    "v1",
                    {"topic": query},
                    GeneratedArticle,
                ),
                max_retries=settings.ai_max_retries,
            )
        except LLMError as exc:
            self.generations.record(
                user_id=user.id,
                kind="article",
                provider=getattr(provider, "name", "unknown"),
                model=getattr(provider, "model", "unknown"),
                prompt_name="article_generation",
                prompt_version="v1",
                status="failed",
                error_code=type(exc).__name__,
            )
            logger.warning(
                "generation.failed", extra={"user_id": user.id, "query_len": len(query)}
            )
            raise ExternalServiceError(
                "Unable to generate content right now. Please try again shortly.",
                code="GENERATION_FAILED",
            ) from exc

        generated: GeneratedArticle = article_response.data
        self.generations.record(
            user_id=user.id,
            kind="article",
            provider=article_response.provider,
            model=article_response.model,
            prompt_name=article_response.prompt_name,
            prompt_version=article_response.prompt_version,
            status="success",
            input_tokens=article_response.input_tokens,
            output_tokens=article_response.output_tokens,
            latency_ms=article_response.latency_ms,
        )

        # --- SEO (separate concern; degrades deterministically) ---
        seo, seo_fallback_used = self._generate_seo(user, provider, generated)

        # --- deterministic rendering + sanitization ---
        markdown = generated.to_markdown()
        html = sanitize_document(render_article_html(generated, seo))

        article = self.articles.create(
            user_id=user.id, title=generated.title, query=query
        )
        self.articles.add_version(
            article,
            version=1,
            content=generated.model_dump_json(),
            change_type="generation",
        )
        self.articles.set_seo(
            article,
            {
                "title": seo.title,
                "description": seo.description,
                "keywords": seo.keywords,
                "og_title": seo.og_title,
                "og_description": seo.og_description,
            },
        )
        self.db.commit()

        logger.info(
            "generation.completed",
            extra={
                "user_id": user.id,
                "article_id": article.id,
                "provider": article_response.provider,
                "seo_fallback": seo_fallback_used,
            },
        )
        return GenerationOutcome(
            article=article,
            markdown=markdown,
            html=html,
            seo=seo,
            seo_fallback_used=seo_fallback_used,
        )

    def _generate_seo(
        self, user: User, provider: LLMProvider, article: GeneratedArticle
    ) -> tuple[SeoResult, bool]:
        try:
            seo_response = call_with_retry(
                lambda: provider.generate(
                    "seo_generation",
                    "v1",
                    {"title": article.title, "introduction": article.introduction},
                    SeoResult,
                ),
                max_retries=settings.ai_max_retries,
            )
        except LLMError as exc:
            self.generations.record(
                user_id=user.id,
                kind="seo",
                provider=getattr(provider, "name", "unknown"),
                model=getattr(provider, "model", "unknown"),
                prompt_name="seo_generation",
                prompt_version="v1",
                status="failed",
                error_code=type(exc).__name__,
            )
            logger.warning("generation.seo_fallback", extra={"user_id": user.id})
            return normalize_seo(_fallback_seo(article)), True

        self.generations.record(
            user_id=user.id,
            kind="seo",
            provider=seo_response.provider,
            model=seo_response.model,
            prompt_name=seo_response.prompt_name,
            prompt_version=seo_response.prompt_version,
            status="success",
            input_tokens=seo_response.input_tokens,
            output_tokens=seo_response.output_tokens,
            latency_ms=seo_response.latency_ms,
        )
        return normalize_seo(seo_response.data), False

    # ------------------------------------------------------------------
    # rewrite
    # ------------------------------------------------------------------
    def rewrite_article(self, user: User, article: Article, style_key: str) -> dict:
        try:
            style = get_style(style_key)
        except ValueError:
            raise BadRequestError(
                f"Unknown rewrite style '{style_key}'.",
                code="UNKNOWN_STYLE",
            ) from None

        latest = self.articles.latest_version(article.id)
        if latest is None:
            raise BadRequestError("Article has no content to rewrite.")

        current = GeneratedArticle.model_validate_json(latest.content)
        if len(current.to_markdown()) > settings.max_rewrite_input_length:
            raise BadRequestError(
                "Article too long to rewrite.", code="REWRITE_INPUT_TOO_LONG"
            )

        try:
            provider = get_provider()
        except ValueError as exc:
            logger.error(
                "generation.provider_unavailable",
                extra={"user_id": user.id, "article_id": article.id},
            )
            raise ExternalServiceError(
                "Content generation is not configured on this server.",
                code="AI_PROVIDER_UNAVAILABLE",
            ) from exc

        try:
            response = call_with_retry(
                lambda: provider.generate(
                    "rewrite",
                    "v1",
                    {
                        "article_markdown": current.to_markdown(),
                        "style_key": style_key,
                        "style_label": style["label"],
                        "style_guidance": style["guidance"],
                    },
                    GeneratedArticle,
                ),
                max_retries=settings.ai_max_retries,
            )
        except LLMError as exc:
            self.generations.record(
                user_id=user.id,
                article_id=article.id,
                kind="rewrite",
                provider=getattr(provider, "name", "unknown"),
                model=getattr(provider, "model", "unknown"),
                prompt_name="rewrite",
                prompt_version="v1",
                status="failed",
                error_code=type(exc).__name__,
            )
            raise ExternalServiceError(
                "Unable to rewrite the article right now. Please try again shortly.",
                code="REWRITE_FAILED",
            ) from exc

        rewritten: GeneratedArticle = response.data
        self.generations.record(
            user_id=user.id,
            article_id=article.id,
            kind="rewrite",
            provider=response.provider,
            model=response.model,
            prompt_name=response.prompt_name,
            prompt_version=response.prompt_version,
            status="success",
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            latency_ms=response.latency_ms,
        )

        next_version = (latest.version or 0) + 1
        self.articles.add_version(
            article,
            version=next_version,
            content=rewritten.model_dump_json(),
            change_type="rewrite",
        )
        article.title = rewritten.title
        self.db.commit()

        logger.info(
            "generation.rewrite_completed",
            extra={"user_id": user.id, "article_id": article.id, "style": style_key},
        )
        return {
            "version": next_version,
            "markdown": rewritten.to_markdown(),
            "html": sanitize_document(render_article_html(rewritten, self._seo_for(article))),
        }

    def _seo_for(self, article: Article) -> SeoResult | None:
        seo_row = self.articles.get_seo(article.id)
        if seo_row is None:
            return None
        return SeoResult(
            title=seo_row.title,
            description=seo_row.description,
            keywords=seo_row.keywords,
            og_title=seo_row.og_title,
            og_description=seo_row.og_description,
            robots=seo_row.robots,
            canonical_url=seo_row.canonical_url,
        )
