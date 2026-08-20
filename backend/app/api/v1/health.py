"""Liveness and readiness probes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

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
