"""Test bootstrap: environment, shared DB fixtures, and API client."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from typing import Any

# Configure environment BEFORE any app import so settings/engine bind to it.
_TMP_DB = os.path.join(tempfile.mkdtemp(prefix="searchscribe-test-"), "test.db")

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["AI_PROVIDER"] = "mock"
os.environ["GEMINI_API_KEY"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.db.models  # noqa: E402  (register models)
from app.core.rate_limit import limiter  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import create_db_engine, get_db  # noqa: E402
from app.main import app  # noqa: E402

TEST_PASSWORD = "correct-horse-1"


def _make_engine():
    # In-memory SQLite shared across connections via StaticPool: one schema,
    # fully isolated per test function, no file cleanup needed.
    return create_db_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture
def db_engine() -> Generator[Any, None, None]:
    engine = _make_engine()
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Any) -> Generator[Session, None, None]:
    factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_engine: Any) -> Generator[TestClient, None, None]:
    factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

    def override_get_db() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    limiter.reset()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    limiter.reset()


def register_user(
    client: TestClient, email: str = "user@example.com", name: str = "Test User"
) -> dict[str, Any]:
    """Helper: sign up and return the TokenOut payload."""
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "name": name, "password": TEST_PASSWORD},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture(autouse=True)
def _reset_mock_provider() -> Generator[None, None, None]:
    """Keep the singleton MockProvider's failure hooks from leaking across tests."""
    from app.ai.factory import get_provider

    provider = get_provider()
    provider.permanent_failure = False
    provider.transient_failures_remaining = 0
    yield
    provider.permanent_failure = False
    provider.transient_failures_remaining = 0


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def generate_article(
    client: TestClient, token: str, query: str = "Urban gardening in small spaces"
) -> dict[str, Any]:
    """Helper: generate an article and return the detail payload."""
    response = client.post(
        "/api/v1/articles",
        json={"query": query},
        headers=auth_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()
