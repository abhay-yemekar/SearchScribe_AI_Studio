"""Application error hierarchy and centralized HTTP exception handlers.

Every error response uses the envelope:

    {"error": {"code": "...", "message": "...", "request_id": "..."}}

Internal details (stack traces, provider errors, SQL) never reach clients.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .logging import request_id_var

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for expected application errors."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    message: str = "Something went wrong. Please try again."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, object] | None = None,
        status_code: int | None = None,
        code: str | None = None,
    ) -> None:
        if message is not None:
            self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        self.details = details
        super().__init__(self.message)


class BadRequestError(AppError):
    status_code = 400
    code = "BAD_REQUEST"


class AuthenticationError(AppError):
    status_code = 401
    code = "AUTHENTICATION_REQUIRED"
    message = "Authentication required."


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"
    message = "You do not have access to this resource."


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    message = "Resource not found."


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"
    message = "The request conflicts with existing state."


class RateLimitError(AppError):
    status_code = 429
    code = "RATE_LIMITED"
    message = "Too many requests. Please slow down and try again shortly."


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "PAYLOAD_TOO_LARGE"
    message = "Request payload is too large."


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "SERVICE_UNAVAILABLE"
    message = "The service is not ready. Please try again shortly."


class ExternalServiceError(AppError):
    status_code = 502
    code = "EXTERNAL_SERVICE_ERROR"
    message = "An upstream service failed. Please try again."


def error_response(
    status_code: int, code: str, message: str, details: dict[str, object] | None = None
) -> JSONResponse:
    error_body: dict[str, object] = {
        "code": code,
        "message": message,
        "request_id": request_id_var.get(),
    }
    if details:
        error_body["details"] = details
    return JSONResponse(status_code=status_code, content={"error": error_body})


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error(
                "app.error",
                extra={"code": exc.code, "status": exc.status_code},
                exc_info=exc,
            )
        return error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        fields = [
            {"field": ".".join(str(p) for p in err["loc"][1:]), "issue": err["msg"]}
            for err in exc.errors()
        ]
        return error_response(
            422,
            "VALIDATION_ERROR",
            "Request validation failed.",
            {"fields": fields},
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return error_response(exc.status_code, "HTTP_ERROR", str(exc.detail))

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Full details go to logs only; the client gets an opaque message.
        logger.error("unhandled.exception", exc_info=exc)
        return error_response(500, "INTERNAL_ERROR", "Something went wrong. Please try again.")
