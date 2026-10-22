"""Optional Sentry error tracking. With no SENTRY_DSN, every function here is a no-op."""

from __future__ import annotations

import logging

import sentry_sdk
from sentry_sdk.types import Event, Hint

from .config import settings

logger = logging.getLogger(__name__)

# Request headers an event may keep. Everything else is dropped: Sentry's scrubber
# doesn't know Cloudflare's or our proxy's client-IP headers (Cf-Connecting-Ip,
# True-Client-Ip, X-Client-IP), and new private headers shouldn't need a code change.
_KEPT_HEADERS = frozenset({"content-type", "content-length", "user-agent"})


def _scrub_request(event: Event, _hint: Hint) -> Event | None:
    request = event.get("request")
    if request:
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = {
                name: value for name, value in headers.items() if name.lower() in _KEPT_HEADERS
            }
        # Query strings carry pagination cursors and search words.
        request.pop("query_string", None)
    return event


def init_sentry() -> bool:
    """Start Sentry once at startup; returns whether it is on."""
    if not settings.sentry_dsn:
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        release=settings.git_sha or None,
        # Errors only: no performance tracing or profiling, to stay in the free tier.
        traces_sample_rate=0.0,
        # No cookies, IP addresses, request bodies or user details leave the server.
        send_default_pii=False,
        max_request_body_size="never",
        # Frame locals hold the raw ASGI scope (bearer token, refresh cookie),
        # passwords and article text, and the scrubber doesn't reach them.
        include_local_variables=False,
        before_send=_scrub_request,
    )
    logger.info("sentry.enabled", extra={"environment": settings.app_env})
    return True


def tag_request(request_id: str) -> None:
    """Attach the request ID to anything Sentry reports for this request."""
    if settings.sentry_dsn:
        sentry_sdk.get_isolation_scope().set_tag("request_id", request_id)


def report_exception(exc: BaseException) -> None:
    """Send an unhandled exception to Sentry, if it is configured."""
    if settings.sentry_dsn:
        sentry_sdk.capture_exception(exc)
