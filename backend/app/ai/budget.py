"""Request-scoped time budgets shared by research, routing and AI adapters."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

from ..core.config import settings
from .base import DeadlineExceededLLMError

_operation_deadline: ContextVar[float | None] = ContextVar("ai_operation_deadline", default=None)
_attempt_deadline: ContextVar[float | None] = ContextVar("ai_attempt_deadline", default=None)


def remaining_operation_seconds() -> float:
    deadline = _operation_deadline.get()
    return max(0.0, deadline - time.monotonic()) if deadline is not None else float(
        settings.ai_operation_timeout_seconds
    )


def effective_timeout_seconds() -> float:
    """Cap one transport by both the operation deadline and any routing reserve."""
    remaining = remaining_operation_seconds()
    attempt_deadline = _attempt_deadline.get()
    if attempt_deadline is not None:
        remaining = min(remaining, attempt_deadline - time.monotonic())
    if remaining <= 0:
        raise DeadlineExceededLLMError("AI operation deadline exhausted")
    return min(float(settings.ai_timeout_seconds), remaining)


@contextmanager
def attempt_budget(seconds: float) -> Iterator[None]:
    token = _attempt_deadline.set(time.monotonic() + max(0.0, seconds))
    try:
        yield
    finally:
        _attempt_deadline.reset(token)


def within_operation_budget[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """Include source retrieval and SEO repair without leaking state between requests."""
    @wraps(fn)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        token = _operation_deadline.set(
            time.monotonic() + settings.ai_operation_timeout_seconds
        )
        try:
            return fn(*args, **kwargs)
        finally:
            _operation_deadline.reset(token)

    return wrapped
