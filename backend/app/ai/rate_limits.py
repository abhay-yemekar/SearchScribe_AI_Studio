"""Extract only safe quota metadata; never retain provider error bodies."""

from __future__ import annotations

import math
import re

from .base import RateLimitedLLMError


def retry_seconds(value: object) -> int | None:
    """Accept a bounded numeric delay, without guessing a provider reset time."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,6}(?:\.\d{1,9})?", value):
        return None
    seconds = math.ceil(float(value))
    return seconds if 1 <= seconds <= 86400 else None


def gemini_rate_limit(details: object, retry_after: str | None) -> RateLimitedLLMError:
    error = details.get("error", {}) if isinstance(details, dict) else {}
    entries = error.get("details", []) if isinstance(error, dict) else []
    daily = False
    delays = [retry_seconds(retry_after)]
    for entry in entries[:32] if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        kind = entry.get("@type", "")
        if kind == "type.googleapis.com/google.rpc.QuotaFailure":
            violations = entry.get("violations", [])
            for violation in violations[:32] if isinstance(violations, list) else []:
                quota_id = violation.get("quotaId", "") if isinstance(violation, dict) else ""
                daily |= isinstance(quota_id, str) and "perday" in quota_id.casefold()
        elif kind == "type.googleapis.com/google.rpc.RetryInfo":
            delay = entry.get("retryDelay")
            if isinstance(delay, str) and delay.endswith("s"):
                delays.append(retry_seconds(delay[:-1]))
    valid = [delay for delay in delays if delay is not None]
    return RateLimitedLLMError(
        "gemini rate limit reached", daily=daily,
        retry_after_seconds=max(valid) if valid else None,
    )


def groq_rate_limit(details: object, retry_after: str | None) -> RateLimitedLLMError:
    error = details.get("error", {}) if isinstance(details, dict) else {}
    message = error.get("message", "") if isinstance(error, dict) else ""
    daily = isinstance(message, str) and bool(re.search(
        r"\b(?:(?:tokens|requests) per day|TPD|RPD)\b", message, flags=re.IGNORECASE,
    ))
    return RateLimitedLLMError(
        "groq rate limit reached", daily=daily, retry_after_seconds=retry_seconds(retry_after),
    )
