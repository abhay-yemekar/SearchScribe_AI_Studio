"""Request-context and security-headers middleware."""

from __future__ import annotations

import logging
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .config import settings
from .exceptions import PayloadTooLargeError, error_response
from .logging import request_id_var
from .observability import report_exception, tag_request

logger = logging.getLogger("http")

AUTH_PATH_PREFIX = "/api/v1/auth"


class RequestContextMiddleware:
    """Give every request a correlation ID, including requests that crash.

    Pure ASGI on purpose. Starlette runs the catch-all Exception handler in
    ServerErrorMiddleware, outside every user middleware, after this request's ID
    is gone: unhandled 500s said "request_id": "-" and had no X-Request-ID. Here the
    exception is handled while the ID is still set, and the 500 then passes back
    through the security-headers and CORS middleware like any other response.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = uuid.uuid4().hex[:12]
        token = request_id_var.set(request_id)
        scope.setdefault("state", {})["request_id"] = request_id
        tag_request(request_id)
        start = time.perf_counter()
        status_code = 500
        started = False

        async def send_with_id(message: Message) -> None:
            nonlocal status_code, started
            if message["type"] == "http.response.start":
                started = True
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception as exc:
            # Full details go to logs (and Sentry) only; the client gets an opaque message.
            logger.error("unhandled.exception", exc_info=exc)
            report_exception(exc)
            if started:
                raise  # Too late for an error response; let the server close it.
            response = error_response(
                500, "INTERNAL_ERROR", "Something went wrong. Please try again."
            )
            await response(scope, receive, send_with_id)
        finally:
            logger.info(
                "http.request",
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "status": status_code,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                },
            )
            request_id_var.reset(token)


class BodySizeLimitMiddleware:
    """Refuse request bodies over MAX_REQUEST_BODY_BYTES before anything parses them.

    A declared Content-Length over the limit is answered at once. A body without
    one (chunked) is counted as it arrives; the 413 raised there passes through
    FastAPI's body reader unchanged and becomes the usual error envelope.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = settings.max_request_body_bytes
        declared = dict(scope["headers"]).get(b"content-length", b"")
        if declared.isdigit() and int(declared) > limit:
            response = error_response(
                413, PayloadTooLargeError.code, PayloadTooLargeError.message
            )
            await response(scope, receive, send)
            return
        received = 0

        async def counted_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise StarletteHTTPException(413, PayloadTooLargeError.message)
            return message

        await self.app(scope, counted_receive, send)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach defensive HTTP headers to every response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
        )
        if request.url.path in {"/docs", "/docs/oauth2-redirect"}:
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'; "
                "script-src 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src https://fastapi.tiangolo.com data:; connect-src 'self'"
            )
        if request.url.path.startswith(AUTH_PATH_PREFIX) or "authorization" in request.headers:
            # Auth and signed-in responses carry tokens or private drafts. Without an
            # explicit header, the Vercel proxy marks them cacheable (public, max-age=0).
            response.headers.setdefault("Cache-Control", "no-store")
        return response
