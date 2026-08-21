"""LLM provider abstraction: protocol, error taxonomy, and bounded retry."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base class for provider failures."""


class TransientLLMError(LLMError):
    """Retryable failure (timeout, 429, 5xx)."""


class PermanentLLMError(LLMError):
    """Non-retryable failure (auth, bad request, safety block)."""


class SchemaValidationError(LLMError):
    """Provider answered but the payload failed schema validation."""


T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class ProviderResponse[T]:
    """A validated provider answer plus observability metadata."""

    data: T
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int
    prompt_name: str
    prompt_version: str


class LLMProvider(Protocol):
    """What every provider must implement. Business logic depends only on this."""

    name: str
    model: str

    def generate(
        self,
        prompt_name: str,
        prompt_version: str,
        variables: dict[str, str],
        schema: type[T],
    ) -> ProviderResponse[T]: ...


def call_with_retry[R](
    fn: Callable[[], R], *, max_retries: int, base_delay_seconds: float = 0.4
) -> R:
    """Run fn() with exponential backoff + jitter on transient failures only.

    Permanent errors and schema failures surface immediately: retrying them
    would only burn tokens on a deterministic outcome.
    """
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except TransientLLMError as exc:
            last_error = exc
            if attempt >= max_retries:
                break
            delay = base_delay_seconds * (2**attempt) + random.uniform(0, 0.25)  # noqa: S311 - jitter only, not crypto
            logger.warning(
                "llm.transient_retry",
                extra={"attempt": attempt + 1, "delay_s": round(delay, 2)},
            )
            time.sleep(delay)
    assert last_error is not None
    raise last_error
