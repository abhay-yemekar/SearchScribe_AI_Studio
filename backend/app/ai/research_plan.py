"""Semantic research intent; the model never selects tools, hosts or date bounds."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..core.config import settings
from .base import LLMError, LLMProvider, ProviderResponse
from .budget import attempt_budget
from .factory import _build_provider


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
    # One bounded call, no retry/fallback multiplication before the actual draft.
    try:
        with attempt_budget(15):
            return provider.generate(
                "research_planning", "v1",
                {"topic_json": json.dumps(query, ensure_ascii=False).replace(
                    "<", "\\u003c"
                ).replace(">", "\\u003e"), "current_date": datetime.now(UTC).date().isoformat()},
                ResearchPlan,
            )
    except LLMError as exc:
        exc.provider, exc.model = provider.name, provider.model
        raise
