"""Database engine and session management."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from ..core.config import settings


def _engine_kwargs(url: str) -> dict[str, object]:
    if url.startswith("sqlite"):
        # Allow FastAPI's threadpool to share the SQLite connection.
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


def create_db_engine(url: str, **kwargs: Any) -> Engine:
    """Build an engine with the same integrity guarantees in dev and production."""
    options = {**_engine_kwargs(url), **kwargs}
    db_engine = create_engine(url, **options)
    if db_engine.dialect.name == "sqlite":
        @event.listens_for(db_engine, "connect")
        def enable_foreign_keys(connection: Any, _record: Any) -> None:
            cursor = connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
            finally:
                cursor.close()
    return db_engine


engine = create_db_engine(settings.database_url)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
