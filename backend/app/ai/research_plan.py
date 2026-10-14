"""Semantic research intent; the model never selects tools, hosts or date bounds."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..core.config import settings
from .base import LLMError, LLMProvider, ProviderResponse, TransientLLMError
from .budget import attempt_budget
from .factory import _build_provider

logger = logging.getLogger(__name__)


class ResearchPlan(BaseModel):
    mode: Literal["reference", "reporting", "general", "historical"]
    requires_current_sources: bool
    primary_sources_only: bool
    supplemental_query: str = Field(max_length=500)
    clarification_question: str = Field(max_length=300)

    @field_validator("supplemental_query", "clarification_question")
    @classmethod
    def plain_text(cls, value: str) -> str:
        return " ".join(value.split())


def research_provider(provider: LLMProvider, *, review: bool = False) -> LLMProvider:
    if review and settings.research_reviewer_provider:
        # Keep review output compatibility separate from article output policy.
        # Local schema and source/passage ownership checks still run before use.
        if settings.research_reviewer_provider == "groq":
            from .groq import GroqProvider

            return GroqProvider(model=settings.research_reviewer_model, json_mode="json_object")
        return _build_provider(
            settings.research_reviewer_provider, settings.research_reviewer_model,
        )
    if settings.research_planner_provider:
        return _build_provider(
            settings.research_planner_provider, settings.research_planner_model,
        )
    return provider


def plan_research(query: str, provider: LLMProvider) -> ProviderResponse[ResearchPlan]:
    provider = research_provider(provider)
    variables = {"topic_json": json.dumps(query, ensure_ascii=False).replace(
        "<", "\\u003c"
    ).replace(">", "\\u003e"), "current_date": datetime.now(UTC).date().isoformat()}

    def attempt(selected: LLMProvider, seconds: int) -> ProviderResponse[ResearchPlan]:
        from .groq import GroqProvider

        if isinstance(selected, GroqProvider):
            selected = GroqProvider(selected.model, reasoning_effort="low", max_output_tokens=1024)
        with attempt_budget(seconds):
            return selected.generate("research_planning", "v1", variables, ResearchPlan)

    # One primary attempt, plus one explicitly configured availability fallback.
    # Never retry refusals, invalid schema, or semantic clarification decisions.
    try:
        try:
            return attempt(provider, 15)
        except TransientLLMError:
            if not settings.research_planner_fallback_provider:
                raise
            provider = _build_provider(
                settings.research_planner_fallback_provider,
                settings.research_planner_fallback_model,
            )
        logger.warning("research.planner_fallback",
                       extra={"provider": provider.name, "model": provider.model})
        return attempt(provider, 10)
    except LLMError as exc:
        exc.provider, exc.model = provider.name, provider.model
        raise
