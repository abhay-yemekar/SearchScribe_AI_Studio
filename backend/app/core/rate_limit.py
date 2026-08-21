"""In-memory sliding-window rate limiting.

Single-process implementation suitable for local dev and single-worker
deployments. The interface is intentionally small so a Redis-backed
implementation can replace it when the backend scales horizontally.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, Request

from .exceptions import RateLimitError

WINDOW_SECONDS = 60


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window: float = WINDOW_SECONDS) -> bool:
        """Record a hit and return whether it is within the limit."""
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            cutoff = now - window
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


def _client_key(request: Request) -> str:
    # Behind a reverse proxy this becomes the proxy IP; deployments should
    # forward and trust X-Forwarded-For at the proxy layer.
    return request.client.host if request.client else "unknown"


def rate_limit(scope: str, limit: int):
    """FastAPI dependency factory limiting requests per client per minute."""

    def dependency(request: Request) -> None:
        if not limiter.allow(f"{scope}:{_client_key(request)}", limit):
            raise RateLimitError(
                details={"retry_after_seconds": WINDOW_SECONDS}
            )

    return Depends(dependency)


__all__ = ["limiter", "rate_limit"]
