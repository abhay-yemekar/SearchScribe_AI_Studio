"""SearchScribe AI Studio — FastAPI application entrypoint."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1.router import api_v1_router
from .core.config import settings
from .core.exceptions import register_exception_handlers
from .core.logging import setup_logging
from .core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    setup_logging(settings.log_level)

    app = FastAPI(
        title="SearchScribe AI Studio API",
        version="2.0.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
    )

    # Order matters: outermost middleware runs first on the way in.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    register_exception_handlers(app)
    app.include_router(api_v1_router)

    logger.info(
        "app.started",
        extra={"env": settings.app_env, "provider": settings.ai_provider},
    )
    return app


app = create_app()
