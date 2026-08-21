"""Data access for generation metadata (observability + cost tracking)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..db.models import Generation


class GenerationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        user_id: int,
        kind: str,
        provider: str,
        model: str,
        prompt_name: str,
        prompt_version: str,
        status: str,
        article_id: int | None = None,
        error_code: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        latency_ms: int | None = None,
    ) -> Generation:
        generation = Generation(
            user_id=user_id,
            article_id=article_id,
            kind=kind,
            provider=provider,
            model=model,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            status=status,
            error_code=error_code,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )
        self.db.add(generation)
        self.db.commit()
        return generation
