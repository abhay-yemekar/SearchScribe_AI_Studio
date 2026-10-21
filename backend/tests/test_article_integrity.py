"""Article integrity: races answer 409, updated_at follows every change, times say UTC."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from conftest import auth_headers, generate_article, register_user
from fastapi.testclient import TestClient

from app.repositories.article_repo import ArticleRepository


def _edit(detail: dict, title: str) -> dict:
    return {
        "base_version": detail["current_version"],
        "content": {**detail["content"], "title": title},
        "seo": detail["seo"],
    }


def _setup(client: TestClient, email: str) -> tuple[dict[str, str], dict]:
    session = register_user(client, email=email)
    return auth_headers(session["access_token"]), generate_article(client, session["access_token"])


def _lose_next_race(monkeypatch: pytest.MonkeyPatch) -> None:
    """The next version check sees version 1, as if a second request committed in between."""
    original = ArticleRepository.latest_version
    calls = 0

    def stale_once(self: ArticleRepository, article_id: int):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return self.get_version(article_id, 1) if calls == 1 else original(self, article_id)

    monkeypatch.setattr(ArticleRepository, "latest_version", stale_once)


# --- F12: concurrent saves and restores --------------------------------------


def test_save_that_loses_a_race_returns_409_not_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers, article = _setup(client, "save-race@example.com")
    url = f"/api/v1/articles/{article['id']}/content"
    assert client.put(url, json=_edit(article, "First save"), headers=headers).status_code == 200

    _lose_next_race(monkeypatch)
    late = client.put(url, json=_edit(article, "Second save"), headers=headers)

    assert late.status_code == 409
    assert late.json()["error"]["code"] == "STALE_ARTICLE_VERSION"
    assert late.json()["error"]["details"]["current_version"] == 2
    current = client.get(f"/api/v1/articles/{article['id']}", headers=headers).json()
    assert current["title"] == "First save"


def test_restore_refuses_a_stale_base_version(client: TestClient) -> None:
    headers, article = _setup(client, "restore-stale@example.com")
    base = f"/api/v1/articles/{article['id']}"
    client.put(f"{base}/content", json=_edit(article, "Edited"), headers=headers)

    stale = client.post(f"{base}/versions/1/restore", json={"base_version": 1}, headers=headers)
    fresh = client.post(f"{base}/versions/1/restore", json={"base_version": 2}, headers=headers)

    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "STALE_ARTICLE_VERSION"
    assert stale.json()["error"]["details"]["current_version"] == 2
    assert fresh.status_code == 200
    assert fresh.json()["current_version"] == 3
    assert fresh.json()["title"] == article["title"]


def test_restore_without_base_version_still_works_for_older_clients(client: TestClient) -> None:
    headers, article = _setup(client, "restore-legacy@example.com")
    base = f"/api/v1/articles/{article['id']}"
    client.put(f"{base}/content", json=_edit(article, "Edited"), headers=headers)

    restored = client.post(f"{base}/versions/1/restore", headers=headers)

    assert restored.status_code == 200
    assert restored.json()["current_version"] == 3


def test_restore_that_loses_a_race_returns_409_not_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers, article = _setup(client, "restore-race@example.com")
    base = f"/api/v1/articles/{article['id']}"
    client.put(f"{base}/content", json=_edit(article, "Edited"), headers=headers)

    _lose_next_race(monkeypatch)
    late = client.post(f"{base}/versions/1/restore", json={"base_version": 1}, headers=headers)

    assert late.status_code == 409
    assert late.json()["error"]["code"] == "STALE_ARTICLE_VERSION"
    versions = client.get(f"{base}/versions", headers=headers).json()["items"]
    assert [item["version"] for item in versions] == [2, 1]


# --- F13: updated_at follows every new version --------------------------------


@pytest.mark.parametrize("change", ["save", "restore", "rewrite"])
def test_updated_at_moves_with_every_new_version(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    headers, article = _setup(client, f"updated-{change}@example.com")
    base = f"/api/v1/articles/{article['id']}"
    if change == "restore":
        client.put(f"{base}/content", json=_edit(article, "Edited"), headers=headers)
        article = client.get(base, headers=headers).json()
    later = datetime(2030, 1, 2, 3, 4, 5)
    monkeypatch.setattr("app.repositories.article_repo.utc_now", lambda: later)

    if change == "save":
        # Same title on purpose: no `articles` column changes, only a new version.
        response = client.put(f"{base}/content", json=_edit(article, article["title"]),
                              headers=headers)
    elif change == "restore":
        response = client.post(f"{base}/versions/1/restore",
                               json={"base_version": article["current_version"]}, headers=headers)
    else:
        response = client.post(f"{base}/rewrite", json={"style": "professional"}, headers=headers)
    assert response.status_code == 200, response.text

    detail = client.get(base, headers=headers).json()
    listed = client.get("/api/v1/articles", headers=headers).json()["items"][0]
    assert detail["updated_at"] == "2030-01-02T03:04:05Z"
    assert listed["updated_at"] == "2030-01-02T03:04:05Z"
    assert detail["created_at"] == article["created_at"]


# --- F15: API times are explicit UTC ------------------------------------------


def _is_utc(value: str) -> bool:
    return value.endswith("Z") and datetime.fromisoformat(value).utcoffset() == UTC.utcoffset(None)


def test_every_api_time_is_utc_with_z(client: TestClient) -> None:
    headers, article = _setup(client, "utc-times@example.com")
    base = f"/api/v1/articles/{article['id']}"

    listed = client.get("/api/v1/articles", headers=headers).json()["items"][0]
    versions = client.get(f"{base}/versions", headers=headers).json()["items"]
    version = client.get(f"{base}/versions/1", headers=headers).json()
    me = client.get("/api/v1/auth/me", headers=headers).json()

    times = [article["created_at"], article["updated_at"], listed["created_at"],
             listed["updated_at"], versions[0]["created_at"], version["created_at"],
             me["created_at"]]
    assert all(_is_utc(value) for value in times), times
