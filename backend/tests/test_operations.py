"""Cross-request reservations, failure recovery and idempotent API behavior."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from conftest import auth_headers, register_user
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.ai.factory import get_provider
from app.core.config import settings
from app.core.exceptions import ConflictError, RateLimitError
from app.core.rate_limit import limiter
from app.db.base import Base, utc_now
from app.db.models import Article, GenerationBudget, GenerationOperation, User
from app.db.session import create_db_engine
from app.services.operation_service import OperationService, complete_operation


def _headers(client, email="writer@example.com", key=None):
    headers = auth_headers(register_user(client, email=email)["access_token"])
    headers["Idempotency-Key"] = key or uuid4().hex
    return headers


def _generate(client, headers, query="A practical guide to urban gardens"):
    return client.post("/api/v1/articles", json={"query": query}, headers=headers)


def test_replay_does_not_call_provider_or_spend_another_slot(client, db_session, monkeypatch):
    headers = _headers(client)
    original = get_provider().generate
    calls = []

    def capture(*args, **kwargs):
        calls.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(get_provider(), "generate", capture)
    first = _generate(client, headers)
    assert first.status_code == 201, first.text
    count = len(calls)
    replay = _generate(client, headers)
    assert replay.status_code == 201
    assert replay.json()["id"] == first.json()["id"]
    assert len(calls) == count > 0
    assert first.headers["X-Generation-Request"] == headers["Idempotency-Key"]
    assert db_session.scalar(select(func.count()).select_from(Article)) == 1
    assert set(db_session.scalars(select(GenerationBudget.count))) == {1}


def test_same_key_cannot_be_reused_for_a_different_payload(client, db_session):
    headers = _headers(client)
    assert _generate(client, headers).status_code == 201
    response = _generate(client, headers, "A different topic entirely")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REQUEST_KEY_REUSED"
    assert db_session.scalar(select(func.count()).select_from(Article)) == 1


def test_request_keys_and_status_are_account_scoped(client):
    key = uuid4().hex
    first = _headers(client, "one@example.com", key)
    second = _headers(client, "two@example.com", key)
    response = _generate(client, first)
    assert response.status_code == 201
    path = f"/api/v1/generation-requests/{key}"
    assert client.get(path, headers=second).status_code == 404
    status = client.get(path, headers=first).json()
    assert status["status"] == "completed"
    assert status["article_id"] == response.json()["id"]
    assert status["result_version"] == 1
    other = _generate(client, second)
    assert other.status_code == 201
    assert other.json()["id"] != response.json()["id"]


def test_deleted_result_never_triggers_another_generation(client):
    headers = _headers(client)
    article_id = _generate(client, headers).json()["id"]
    assert client.delete(f"/api/v1/articles/{article_id}", headers=headers).status_code == 204
    response = _generate(client, headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "GENERATION_RESULT_REMOVED"


def test_failed_request_remains_failed_even_after_provider_recovers(client, db_session):
    headers = _headers(client)
    get_provider().permanent_failure = True
    assert _generate(client, headers).status_code == 502
    get_provider().permanent_failure = False
    response = _generate(client, headers)
    assert response.status_code == 409
    assert client.get(f"/api/v1/generation-requests/{headers['Idempotency-Key']}",
                      headers=headers).json()["status"] == "failed"
    assert db_session.scalar(select(func.count()).select_from(Article)) == 0


def test_daily_limit_allows_replay_read_edit_and_export(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "generation_daily_user_limit", 1)
    headers = _headers(client)
    first = _generate(client, headers)
    assert first.status_code == 201
    article_id = first.json()["id"]
    assert _generate(client, headers).status_code == 201
    another = {**headers, "Idempotency-Key": uuid4().hex}
    response = _generate(client, another)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "GENERATION_DAILY_LIMIT"
    assert int(response.headers["Retry-After"]) > 0
    assert client.get(f"/api/v1/articles/{article_id}", headers=headers).status_code == 200
    assert client.patch(f"/api/v1/articles/{article_id}", json={"title": "A saved title"},
                        headers=headers).status_code == 200
    # Rejected reservations roll back the global bucket as well.
    assert set(db_session.scalars(select(GenerationBudget.count))) == {1}
    assert db_session.scalar(select(func.count()).select_from(GenerationOperation)) == 1


def test_global_limit_is_shared_by_accounts(client, monkeypatch):
    monkeypatch.setattr(settings, "generation_daily_global_limit", 1)
    first = _headers(client, "first@example.com")
    second = _headers(client, "second@example.com")
    assert _generate(client, first).status_code == 201
    assert _generate(client, second).status_code == 429


def test_rewrite_replay_creates_one_version_and_shares_the_daily_budget(client, db_session):
    headers = _headers(client)
    detail = _generate(client, headers).json()
    headers["Idempotency-Key"] = uuid4().hex
    path = f"/api/v1/articles/{detail['id']}/rewrite"
    first = client.post(path, json={"style": "minimal"}, headers=headers)
    assert first.status_code == 200, first.text
    replay = client.post(path, json={"style": "minimal"}, headers=headers)
    assert replay.json()["current_version"] == 2
    assert set(db_session.scalars(select(GenerationBudget.count))) == {2}


@pytest.mark.parametrize("key", ["short", "x" * 65, "a/" * 10])
def test_invalid_key_does_not_generate(client, db_session, key):
    response = _generate(client, _headers(client, key=key))
    assert response.status_code == 400
    assert db_session.scalar(select(func.count()).select_from(GenerationOperation)) == 0


def test_processing_and_interrupted_requests_are_not_reexecuted(client, db_session):
    headers = _headers(client)
    user_id = db_session.scalar(select(User.id))
    assert user_id is not None
    operation, _ = OperationService(db_session).reserve(
        user_id, headers["Idempotency-Key"], "generation",
        {"query": "A practical guide to urban gardens"},
    )
    OperationService(db_session).clear_context()
    response = _generate(client, headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "GENERATION_IN_PROGRESS"
    db_session.execute(update(GenerationOperation).where(GenerationOperation.id == operation.id)
                       .values(deadline_at=utc_now() - timedelta(seconds=1)))
    db_session.commit()
    status = client.get(f"/api/v1/generation-requests/{headers['Idempotency-Key']}",
                        headers=headers).json()
    assert status["status"] == "interrupted"
    assert _generate(client, headers).json()["error"]["code"] == "GENERATION_INTERRUPTED"
    assert db_session.scalar(select(func.count()).select_from(Article)) == 0


def test_daily_rollover_and_restart_keep_committed_reservations(db_engine, db_session, monkeypatch):
    user = User(email="reserve@example.com", name="Reserve", password_hash="test")
    db_session.add(user)
    db_session.commit()
    user_id = user.id
    key = uuid4().hex
    first, _ = OperationService(db_session).reserve(user_id, key, "generation", {"query": "topic"})
    with Session(db_engine) as restarted:
        with pytest.raises(ConflictError):
            OperationService(restarted).reserve(user_id, key, "generation", {"query": "topic"})
        future = utc_now() + timedelta(days=1)
        monkeypatch.setattr("app.services.operation_service.utc_now", lambda: future)
        new, fresh = OperationService(restarted).reserve(
            user_id, uuid4().hex, "generation", {"query": "tomorrow"},
        )
        assert fresh and new.id != first.id
        assert set(restarted.scalars(select(GenerationBudget.count))) == {1}


@pytest.mark.parametrize("same_key,expected", [(False, 3), (True, 1)])
def test_concurrent_reservations_are_atomic(
    db_engine, tmp_path, monkeypatch, same_key, expected,
):
    monkeypatch.setattr(settings, "generation_daily_global_limit", 3)
    # SQLite needs independent file connections; StaticPool is deliberately shared
    # by normal unit tests. The Postgres CI job exercises its real row locking.
    sqlite = db_engine.dialect.name == "sqlite"
    engine = create_db_engine(f"sqlite:///{tmp_path / 'concurrency.db'}") if sqlite else db_engine
    if sqlite:
        Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    try:
        with factory() as setup:
            user = User(email="concurrent@example.com", name="Concurrent", password_hash="test")
            setup.add(user)
            setup.commit()
            user_id = user.id

        shared_key = uuid4().hex

        def reserve(index):
            with factory() as db:
                try:
                    OperationService(db).reserve(
                        user_id, shared_key if same_key else uuid4().hex,
                        "generation", {"i": 0 if same_key else index},
                    )
                    return True
                except (RateLimitError, ConflictError):
                    return False

        with ThreadPoolExecutor(max_workers=8) as pool:
            accepted = list(pool.map(reserve, range(8)))
        assert sum(accepted) == expected
        with factory() as db:
            assert set(db.scalars(select(GenerationBudget.count))) == {expected}
            assert db.scalar(select(func.count()).select_from(GenerationOperation)) == expected
    finally:
        if sqlite:
            engine.dispose()


def test_invalid_rewrite_and_unowned_article_do_not_spend_slots(client, db_session):
    headers = _headers(client)
    detail = _generate(client, headers).json()
    limiter.reset()
    headers["Idempotency-Key"] = uuid4().hex
    response = client.post(f"/api/v1/articles/{detail['id']}/rewrite",
                           json={"style": "unknown"}, headers=headers)
    assert response.status_code == 400
    other = _headers(client, "outsider@example.com")
    assert client.post(f"/api/v1/articles/{detail['id']}/rewrite",
                       json={"style": "minimal"}, headers=other).status_code == 404
    assert set(db_session.scalars(select(GenerationBudget.count))) == {1}


def test_expired_operation_cannot_commit_an_article_without_a_matching_result(db_session):
    user = User(email="expired@example.com", name="Expired", password_hash="test")
    db_session.add(user)
    db_session.commit()
    operation, _ = OperationService(db_session).reserve(
        user.id, uuid4().hex, "generation", {"query": "topic"},
    )
    db_session.execute(update(GenerationOperation).where(GenerationOperation.id == operation.id)
                       .values(deadline_at=utc_now() - timedelta(seconds=1)))
    db_session.commit()
    article = Article(user_id=user.id, title="Should not survive", query="topic", status="ready")
    db_session.add(article)
    db_session.flush()
    with pytest.raises(ConflictError):
        complete_operation(db_session, article.id, 1)
    db_session.rollback()
    assert db_session.scalar(select(func.count()).select_from(Article)) == 0
