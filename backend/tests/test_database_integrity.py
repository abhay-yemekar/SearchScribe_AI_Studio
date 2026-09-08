"""Integrity guarantees must apply to every engine created by the application."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.session import create_db_engine


def test_sqlite_rejects_orphaned_children() -> None:
    engine = create_db_engine("sqlite://")
    try:
        with engine.begin() as connection:
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
            connection.execute(text("CREATE TABLE parent (id INTEGER PRIMARY KEY)"))
            connection.execute(text(
                "CREATE TABLE child (parent_id INTEGER REFERENCES parent(id))"
            ))
            with pytest.raises(IntegrityError):
                connection.execute(text("INSERT INTO child VALUES (123)"))
    finally:
        engine.dispose()
