"""Deterministic offline provider for tests and keyless local development."""

from __future__ import annotations

import time
from typing import TypeVar, cast

from pydantic import BaseModel

from .base import PermanentLLMError, ProviderResponse, TransientLLMError
from .schemas import ArticleSection, GeneratedArticle, SeoResult

T = TypeVar("T", bound=BaseModel)


class MockProvider:
    name = "mock"
    model = "mock-1"

    def __init__(self) -> None:
        # Test hooks: raise N transient errors before succeeding; or fail hard.
        self.transient_failures_remaining = 0
        self.permanent_failure = False

    def generate(
        self,
        prompt_name: str,
        prompt_version: str,
        variables: dict[str, str],
        schema: type[T],
    ) -> ProviderResponse[T]:
        if self.permanent_failure:
            raise PermanentLLMError("mock: configured permanent failure")
        if self.transient_failures_remaining > 0:
            self.transient_failures_remaining -= 1
            raise TransientLLMError("mock: transient failure")

        started = time.perf_counter()
        if schema is GeneratedArticle:
            if prompt_name == "rewrite":
                data: object = self._rewrite_article(variables)
            else:
                data = self._generate_article(variables)
        elif schema is SeoResult:
            data = self._generate_seo(variables)
        else:
            raise PermanentLLMError(f"mock: unsupported schema {schema.__name__}")

        return ProviderResponse(
            data=cast("T", data),
            provider=self.name,
            model=self.model,
            input_tokens=120,
            output_tokens=800,
            latency_ms=int((time.perf_counter() - started) * 1000),
            prompt_name=prompt_name,
            prompt_version=prompt_version,
        )

    def _generate_article(self, variables: dict[str, str]) -> GeneratedArticle:
        topic = variables.get("topic", "Untitled Topic")[:160]
        return GeneratedArticle(
            title=f"A Practical Guide to {topic}",
            introduction=(
                f"This mock article about {topic} was generated offline by the "
                "deterministic MockProvider. It exercises the full pipeline "
                "without an API key."
            ),
            sections=[
                ArticleSection(
                    heading=f"Why {topic} Matters",
                    paragraphs=[
                        f"Understanding {topic} starts with the fundamentals.",
                        "Mock content keeps local development fast and free.",
                    ],
                    bullets=[f"{topic} basics", "Key considerations"],
                ),
                ArticleSection(
                    heading=f"Getting Started with {topic}",
                    paragraphs=[
                        f"The first step with {topic} is defining your goal.",
                    ],
                ),
            ],
            conclusion=(
                f"{topic} rewards consistent, practical effort. This mock "
                "conclusion completes the structure."
            ),
        )

    def _rewrite_article(self, variables: dict[str, str]) -> GeneratedArticle:
        return self._generate_article(
            {"topic": variables.get("style_label", "Rewritten") + " Article"}
        )

    def _generate_seo(self, variables: dict[str, str]) -> SeoResult:
        title = variables.get("title", "Mock Article")
        return SeoResult(
            title=f"{title[:45]} | Mock Guide",
            description=(
                f"A practical mock overview of {title[:60]}. Generated offline "
                "for development and testing."
            )[:160],
            keywords=[title.lower()[:40], "mock", "searchscribe", "guide"],
            og_title=f"{title[:50]} — Mock",
            og_description=f"Offline mock article about {title[:70]}."[:160],
        )
