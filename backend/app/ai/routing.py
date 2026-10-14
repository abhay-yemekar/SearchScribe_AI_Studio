"""Bounded primary retries with one explicitly configured transient-only fallback."""

from __future__ import annotations

import logging
from collections.abc import Callable

from ..core.config import settings
from .base import LLMError, LLMProvider, RateLimitedLLMError, TransientLLMError, call_with_retry
from .budget import attempt_budget, effective_timeout_seconds, remaining_operation_seconds
from .factory import get_fallback_provider

logger = logging.getLogger(__name__)


def _attempt[R](provider: LLMProvider, fn: Callable[[LLMProvider], R]) -> R:
    try:
        effective_timeout_seconds()
        result = fn(provider)
        effective_timeout_seconds()
        return result
    except LLMError as exc:
        # The failure belongs to this invocation, never shared mutable router state.
        failure = (RateLimitedLLMError(str(exc), daily=exc.daily,
                                       retry_after_seconds=exc.retry_after_seconds)
                   if isinstance(exc, RateLimitedLLMError) else type(exc)(str(exc)))
        failure.provider = provider.name
        failure.model = provider.model
        raise failure from None


def call_with_fallback[R](provider: LLMProvider, fn: Callable[[LLMProvider], R]) -> R:
    fallback = get_fallback_provider() if provider.name != "mock" else None
    remaining = remaining_operation_seconds()
    # Preserve a useful fallback window instead of spending the whole deadline
    # on repeated primary timeouts. The fallback still has only one external call.
    reserve = min(20.0, remaining / 3) if fallback is not None else 0.0
    try:
        with attempt_budget(remaining - reserve):
            return call_with_retry(
                lambda: _attempt(provider, fn), max_retries=settings.ai_max_retries,
            )
    except TransientLLMError:
        if fallback is None:
            raise
    effective_timeout_seconds()
    logger.warning(
        "llm.fallback", extra={"provider": fallback.name, "model": fallback.model},
    )
    return _attempt(fallback, fn)
