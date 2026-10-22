"""Liveness and readiness probes."""

from __future__ import annotations

import hmac
import logging
from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.exceptions import ServiceUnavailableError
from ...db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
def health() -> dict[str, str]:
    """Process is up. Cheap by design; no dependency checks."""
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe")
def ready(db: Session = Depends(get_db)) -> dict[str, str]:
    """Process is up and required dependencies are reachable."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("readiness.database_failed")
        raise ServiceUnavailableError("Database is not reachable.") from None
    return {"status": "ready"}


@lru_cache
def _code_head() -> str | None:
    # backend/alembic.ini: the migration head this code expects.
    ini = Path(__file__).resolve().parents[3] / "alembic.ini"
    return ScriptDirectory.from_config(Config(str(ini))).get_current_head()


@router.get("/version", summary="Deployed commit and database migration state")
def version(db: Session = Depends(get_db)) -> dict[str, str | None]:
    """Which code is running, and whether its migrations are applied.

    `alembic_revision` is what the database is at; it should equal `alembic_head`.
    """
    try:
        revision = db.scalar(text("SELECT version_num FROM alembic_version"))
    except SQLAlchemyError:
        db.rollback()
        revision = None
    return {
        "git_sha": settings.git_sha or "unknown",
        "alembic_head": _code_head(),
        "alembic_revision": revision,
        "environment": settings.app_env,
    }


@router.post("/debug/sentry-test", include_in_schema=False)
def sentry_test(x_sentry_test_token: str = Header(default="")) -> None:
    """Crash on purpose, to check that a live 500 reaches Sentry with its request ID.

    Without the configured token this answers exactly like an unknown path.
    """
    expected = settings.sentry_test_token
    if len(expected) < 32 or not hmac.compare_digest(
        x_sentry_test_token.encode(), expected.encode()
    ):
        raise HTTPException(status_code=404, detail="Not Found")
    raise RuntimeError("Deliberate Sentry test error")
