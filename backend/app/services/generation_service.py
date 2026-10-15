"""Generation pipeline: query -> combined article/SEO -> safe HTML -> persistence.

Failure policy: provider failures NEVER produce fake content. A failed article
generation records a failed Generation row and raises ExternalServiceError.
Missing or invalid SEO gets one repair. Repair failure keeps the valid article
and derives editable metadata from its wording, visibly marked needs_review.
"""

from __future__ import annotations

import logging
import re
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from ..ai.base import LLMError, LLMProvider, RateLimitedLLMError, SchemaValidationError
from ..ai.budget import (
    attempt_budget,
    effective_timeout_seconds,
    remaining_operation_seconds,
    within_operation_budget,
)
from ..ai.draft_review import (
    DRAFT_RECHECK_PROMPT_VERSION,
    DRAFT_REVIEW_PROMPT_VERSION,
    apply_review,
    recheck_draft,
    review_draft,
)
from ..ai.evidence_review import review_evidence, select_evidence
from ..ai.factory import get_provider
from ..ai.renderer import _fallback_seo, render_article_html
from ..ai.research import ResearchResult, needs_current_sources, retrieve_sources
from ..ai.research_plan import ResearchPlan, plan_research
from ..ai.routing import call_with_fallback
from ..ai.sanitizer import sanitize_document
from ..ai.schemas import (
    GeneratedArticle,
    GeneratedArticleWithSeo,
    ResearchSummary,
    SeoCandidate,
    SeoResult,
)
from ..ai.styles import get_style
from ..ai.validation import validate_generated_seo
from ..core.config import settings
from ..core.exceptions import BadRequestError, ExternalServiceError, ServiceUnavailableError
from ..db.models import Article, User
from ..repositories.article_repo import ArticleRepository
from ..repositories.generation_repo import GenerationRepository

logger = logging.getLogger(__name__)


def _raise_provider_limit(exc: LLMError) -> None:
    if not isinstance(exc, RateLimitedLLMError):
        return
    details: dict[str, object] = {}
    delay = exc.retry_after_seconds
    if isinstance(delay, int) and not isinstance(delay, bool) and 1 <= delay <= 86400:
        details = {
            "retry_after_seconds": delay,
            "retry_at": (datetime.now(UTC) + timedelta(seconds=delay)).isoformat(),
        }
    raise ServiceUnavailableError(
        ("The AI service has reached its daily limit. Please try again later. " if exc.daily
         else "The AI service is temporarily busy. Please try again later. ")
        + "Your topic and saved articles are unchanged.",
        code="AI_DAILY_LIMIT_REACHED" if exc.daily else "AI_SERVICE_BUSY",
        details=details,
    ) from exc


def _claimed_source_ids(article: GeneratedArticle) -> set[str]:
    # A generated Sources appendix is not evidence that the body attributes claims.
    body = article.model_copy(update={"research": ResearchSummary()}).to_markdown()
    brackets = re.findall(r"\[[^\]\n]*\]", body)
    return {source_id for bracket in brackets for source_id in re.findall(r"\bS\d+\b", bracket)}


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
    @within_operation_budget
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

        # Plan only when live search is configured. Mock remains fully offline.
        plan: ResearchPlan | None = None
        if provider.name != "mock" and settings.tavily_api_key.strip():
            try:
                planning = plan_research(query, provider)
            except LLMError as exc:
                self.generations.record(
                    user_id=user.id, kind="research_plan", provider=exc.provider or provider.name,
                    model=exc.model or provider.model, prompt_name="research_planning",
                    prompt_version="v1", status="failed", error_code=type(exc).__name__,
                )
                _raise_provider_limit(exc)
                raise ExternalServiceError(
                    "Unable to prepare research right now. Your topic has been kept; try again.",
                    code="RESEARCH_PLANNING_UNAVAILABLE",
                ) from exc
            plan = planning.data
            self.generations.record(
                user_id=user.id, kind="research_plan", provider=planning.provider,
                model=planning.model, prompt_name=planning.prompt_name,
                prompt_version=planning.prompt_version, status="success",
                input_tokens=planning.input_tokens, output_tokens=planning.output_tokens,
                latency_ms=planning.latency_ms,
            )
            if plan.clarification_question:
                raise BadRequestError(
                    plan.clarification_question,
                    code="TOPIC_CLARIFICATION_REQUIRED",
                    details={"hint": "Add this detail to your topic, then generate again."},
                )
        # Mock preview/tests never retrieve live pages or consume provider credits.
        research = (
            (retrieve_sources(query, plan=plan) if plan else retrieve_sources(query))
            if provider.name != "mock"
            else ResearchResult(ResearchSummary(), "Offline mock preview; no live research.")
        )
        if plan is not None and research.summary.sources:
            review_provider, review_model = provider.name, provider.model
            try:
                assessment = review_evidence(query, research, plan, provider)
                review_provider, review_model = assessment.provider, assessment.model
                research = select_evidence(research, assessment.data,
                                           primary_only=plan.primary_sources_only)
            except LLMError as exc:
                self.generations.record(
                    user_id=user.id, kind="evidence_review",
                    provider=exc.provider or review_provider, model=exc.model or review_model,
                    prompt_name="evidence_review", prompt_version="v1", status="failed",
                    error_code=type(exc).__name__,
                )
                _raise_provider_limit(exc)
                raise ExternalServiceError(
                    "Unable to select reliable evidence for this draft right now. "
                    "Your topic has been kept; try again.", code="EVIDENCE_REVIEW_UNAVAILABLE",
                ) from exc
            self.generations.record(
                user_id=user.id, kind="evidence_review", provider=assessment.provider,
                model=assessment.model, prompt_name=assessment.prompt_name,
                prompt_version=assessment.prompt_version, status="success",
                input_tokens=assessment.input_tokens, output_tokens=assessment.output_tokens,
                latency_ms=assessment.latency_ms,
            )
        if (
            provider.name != "mock"
            and ((plan.requires_current_sources or plan.primary_sources_only)
                 if plan else needs_current_sources(query))
            and not research.summary.sources
        ):
            if research.failure == "not_configured":
                raise ExternalServiceError(
                    "Live web research is not configured on this server. "
                    "A current-events draft cannot be generated yet.",
                    code="RESEARCH_NOT_CONFIGURED",
                )
            if research.failure == "no_evidence":
                raise ExternalServiceError(
                    research.failure_message or (
                        "Search returned no usable relevant evidence for this topic. "
                        "Try a more specific topic or include the post's title and date."
                    ),
                    code="CURRENT_SOURCES_NOT_FOUND",
                )
            raise ExternalServiceError(
                "Live web research is temporarily unavailable. No current-events draft was "
                "generated. Please try again shortly.", code="CURRENT_SOURCES_UNAVAILABLE",
            )

        # --- article ---
        generation_variables = {
            "topic": query,
            "current_date": datetime.now(UTC).date().isoformat(),
            "research_status": research.summary.status,
            "research_context": research.context,
        }
        try:
            remaining = remaining_operation_seconds()
            # Research and checking share the original request deadline. Nested
            # routing budgets cannot spend this reserve on writer retries.
            writing_budget = (attempt_budget(remaining - min(40, remaining / 2))
                              if settings.draft_review_enabled and provider.name != "mock"
                              and research.summary.sources
                              else nullcontext())
            with writing_budget:
                article_response, selected_provider = call_with_fallback(
                    provider, lambda selected: (selected.generate(
                        "article_generation",
                        "v5",
                        generation_variables,
                        GeneratedArticleWithSeo,
                    ), selected),
                )
            # Discard model-provided metadata before inspecting the actual draft.
            article_response.data.research = research.summary
            source_ids = {source.id for source in research.summary.sources}
            claimed_ids = _claimed_source_ids(article_response.data)
            if not claimed_ids.issubset(source_ids) or (source_ids and not claimed_ids):
                failure = SchemaValidationError("Article citations are missing or unsupported")
                failure.provider = article_response.provider
                failure.model = article_response.model
                raise failure
        except LLMError as exc:
            self.generations.record(
                user_id=user.id,
                kind="article",
                provider=exc.provider or provider.name,
                model=exc.model or provider.model,
                prompt_name="article_generation",
                prompt_version="v5",
                status="failed",
                error_code=type(exc).__name__,
            )
            logger.warning("generation.failed", extra={"user_id": user.id, "query_len": len(query)})
            _raise_provider_limit(exc)
            raise ExternalServiceError(
                "Unable to generate content right now. Please try again shortly.",
                code="GENERATION_FAILED",
            ) from exc

        generated = GeneratedArticle.model_validate(
            article_response.data.model_dump(exclude={"seo"})
        )
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

        # The normal path is one call. A valid article survives an invalid SEO answer.
        seo, seo_fallback_used = self._resolve_seo(
            user, selected_provider, generated, article_response.data.seo
        )

        if settings.draft_review_enabled and provider.name != "mock" and research.summary.sources:
            generated, reviewed_seo = self._review_draft(
                user, query, generated, seo, research, selected_provider,
            )
            assert reviewed_seo is not None
            seo = reviewed_seo

        # --- deterministic rendering + sanitization ---
        markdown = generated.to_markdown()
        html = sanitize_document(render_article_html(generated, seo))

        article = self.articles.create(user_id=user.id, title=generated.title, query=query)
        self.articles.add_version(
            article,
            version=1,
            content=generated.model_dump_json(),
            change_type="generation",
            seo_snapshot=seo.model_dump_json(),
        )
        self.articles.set_seo(
            article,
            {
                "title": seo.title,
                "description": seo.description,
                "keywords": seo.keywords,
                "og_title": seo.og_title,
                "og_description": seo.og_description,
                "canonical_url": seo.canonical_url,
                "robots": seo.robots,
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

    def _review_draft(
        self, user: User, query: str, article: GeneratedArticle, seo: SeoResult | None,
        research: ResearchResult, provider: LLMProvider,
    ) -> tuple[GeneratedArticle, SeoResult | None]:
        """One evidence edit and one changed-text recheck within the same deadline."""
        review_provider, review_model = provider.name, provider.model
        stage = "draft_review"
        try:
            response = review_draft(query, article, seo, research, provider)
            review_provider, review_model = response.provider, response.model
            findings = any(block.verdict == "revise" for block in response.data.blocks)
            self.generations.record(
                user_id=user.id, kind="draft_review", provider=response.provider,
                model=response.model, prompt_name=response.prompt_name,
                prompt_version=response.prompt_version, status="success",
                input_tokens=response.input_tokens, output_tokens=response.output_tokens,
                latency_ms=response.latency_ms,
                error_code="DRAFT_REVISION_REQUIRED" if findings else None,
            )
            if not findings:
                return article, seo
            article, seo, changed = apply_review(article, seo, research, response.data)
            source_ids = {source.id for source in research.summary.sources}
            cited_ids = _claimed_source_ids(article)
            if not cited_ids or not cited_ids.issubset(source_ids):
                raise SchemaValidationError("Evidence correction lost the draft citations")
            stage = "draft_recheck"
            confirmation = recheck_draft(
                query, article, seo, research, provider, only_ids=changed,
            )
            review_provider, review_model = confirmation.provider, confirmation.model
            self.generations.record(
                user_id=user.id, kind="draft_review", provider=confirmation.provider,
                model=confirmation.model, prompt_name=confirmation.prompt_name,
                prompt_version=confirmation.prompt_version, status="success",
                input_tokens=confirmation.input_tokens, output_tokens=confirmation.output_tokens,
                latency_ms=confirmation.latency_ms,
                error_code="DRAFT_EVIDENCE_CONFLICT" if confirmation.data.issues else None,
            )
            if confirmation.data.issues:
                raise ExternalServiceError(
                    "The draft still contained claims the retrieved excerpts could not "
                    "support after one correction. No new article was saved. "
                    "Try a narrower topic or more specific source details.",
                    code="DRAFT_EVIDENCE_CONFLICT",
                )
            return article, seo
        except LLMError as exc:
            self.generations.record(
                user_id=user.id, kind="draft_review",
                provider=exc.provider or review_provider, model=exc.model or review_model,
                prompt_name=stage,
                prompt_version=(DRAFT_REVIEW_PROMPT_VERSION if stage == "draft_review"
                                else DRAFT_RECHECK_PROMPT_VERSION), status="failed",
                error_code=type(exc).__name__,
            )
            _raise_provider_limit(exc)
            raise ExternalServiceError(
                "The draft's evidence check could not finish. No new article was saved. "
                "Your topic has been kept; please try again shortly.",
                code="DRAFT_REVIEW_UNAVAILABLE",
            ) from exc

    def _resolve_seo(
        self, user: User, provider: LLMProvider, article: GeneratedArticle,
        candidate: SeoCandidate | None,
    ) -> tuple[SeoResult, bool]:
        seo = validate_generated_seo(candidate)
        if seo is not None:
            return seo, False
        try:
            # Exactly one targeted repair, including on transient errors; do not
            # discard a good article or multiply requests to fix its metadata.
            effective_timeout_seconds()
            seo_response = provider.generate(
                "seo_generation", "v3",
                {"article_json": article.model_dump_json().replace(
                    "<", "\\u003c"
                ).replace(">", "\\u003e")},
                SeoCandidate,
            )
            seo = validate_generated_seo(seo_response.data)
            if seo is None:
                raise SchemaValidationError("Repaired SEO did not meet product bounds")
        except LLMError as exc:
            self.generations.record(
                user_id=user.id,
                kind="seo",
                provider=getattr(provider, "name", "unknown"),
                model=getattr(provider, "model", "unknown"),
                prompt_name="seo_generation",
                prompt_version="v3",
                status="failed",
                error_code=type(exc).__name__,
            )
            logger.warning("generation.seo_fallback", extra={"user_id": user.id})
            return _fallback_seo(article), True

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
        return seo, False

    # ------------------------------------------------------------------
    # rewrite
    # ------------------------------------------------------------------
    @within_operation_budget
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
            raise BadRequestError("Article too long to rewrite.", code="REWRITE_INPUT_TOO_LONG")

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
            response = call_with_fallback(
                provider, lambda selected: selected.generate(
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
            )
            response.data.research = current.research
            source_ids = {source.id for source in current.research.sources}
            claimed_ids = _claimed_source_ids(response.data)
            if not claimed_ids.issubset(source_ids):
                failure = SchemaValidationError("Rewrite contains an unsupported citation")
                failure.provider = response.provider
                failure.model = response.model
                raise failure
        except LLMError as exc:
            self.generations.record(
                user_id=user.id,
                article_id=article.id,
                kind="rewrite",
                provider=exc.provider or provider.name,
                model=exc.model or provider.model,
                prompt_name="rewrite",
                prompt_version="v1",
                status="failed",
                error_code=type(exc).__name__,
            )
            _raise_provider_limit(exc)
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
        current_seo = self._seo_for(article)
        if current_seo is not None:
            current_seo.review_status = "needs_review"
        self.articles.add_version(
            article,
            version=next_version,
            content=rewritten.model_dump_json(),
            change_type="rewrite",
            seo_snapshot=current_seo.model_dump_json() if current_seo else None,
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
