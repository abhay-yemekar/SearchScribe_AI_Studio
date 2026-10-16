"""In-memory sliding-window rate limiting.

Single-process implementation suitable for local dev and single-worker
deployments. The interface is intentionally small so a Redis-backed
implementation can replace it when the backend scales horizontally.
"""

from __future__ import annotations

import hmac
import ipaddress
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any

from fastapi import Depends, Request

from .config import settings
from .exceptions import RateLimitError

WINDOW_SECONDS = 60
# Set only by frontend/proxy.ts, which overwrites any value the browser sent.
CLIENT_IP_HEADER = "x-client-ip"
PROXY_SECRET_HEADER = "x-proxy-secret"  # noqa: S105 - header name, not a secret


class SlidingWindowLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._longest_window = 0.0
        self._next_sweep = 0.0

    def allow(self, key: str, limit: int, window: float = WINDOW_SECONDS) -> bool:
        """Record a hit and return whether it is within the limit."""
        now = self._clock()
        with self._lock:
            self._longest_window = max(self._longest_window, window)
            if now >= self._next_sweep:
                self._sweep(now - self._longest_window)
                self._next_sweep = now + self._longest_window
            bucket = self._hits[key]
            cutoff = now - window
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True

    def _sweep(self, cutoff: float) -> None:
        # Keys are per client, account and session, so drop idle ones to bound memory.
        idle = [key for key, hits in self._hits.items() if not hits or hits[-1] <= cutoff]
        for key in idle:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
    """The caller's IP address for rate limits and abuse budgets.

    Behind Vercel and Render the ASGI peer is a proxy shared by every user, so
    the frontend proxy forwards the real address in X-Client-IP. That header is
    trusted only when it arrives with PROXY_SHARED_SECRET; anything else (direct
    calls to the API, a missing or wrong secret, a malformed address) falls back
    to the peer. Generic forwarding headers such as X-Forwarded-For are never read.
    """
    peer = request.client.host if request.client else "unknown"
    secret = settings.proxy_shared_secret
    if not secret:
        return peer
    presented = request.headers.get(PROXY_SECRET_HEADER, "")
    if not hmac.compare_digest(presented.encode(), secret.encode()):
        return peer
    try:
        return str(ipaddress.ip_address(request.headers.get(CLIENT_IP_HEADER, "").strip()))
    except ValueError:
        return peer


def enforce(key: str, limit: int) -> None:
    """Count one request against ``key`` and raise 429 once it exceeds ``limit``."""
    if not limiter.allow(key, limit):
        raise RateLimitError(details={"retry_after_seconds": WINDOW_SECONDS})


def rate_limit(scope: str, limit: int, key: Callable[[Request], str] = client_ip) -> Any:
    """FastAPI dependency factory limiting requests per key (default: client IP) per minute."""

    def dependency(request: Request) -> None:
        enforce(f"{scope}:{key(request)}", limit)

    return Depends(dependency)


__all__ = ["client_ip", "enforce", "limiter", "rate_limit"]
