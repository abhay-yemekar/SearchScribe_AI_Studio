"""Article API: generation, pagination, isolation, rewrite, versions."""

from __future__ import annotations

from conftest import auth_headers, generate_article, register_user
from fastapi.testclient import TestClient


def test_generate_article_returns_full_detail(client: TestClient) -> None:
    tokens = register_user(client, email="gen@example.com")
    detail = generate_article(client, tokens["access_token"])

    assert detail["title"]
    assert detail["markdown"].startswith("# ")
    assert "<!DOCTYPE html>" in detail["html"]
    assert detail["seo"] is not None
    assert detail["seo"]["keywords"]
    assert detail["current_version"] == 1
    assert detail["status"] == "ready"


def test_generate_rejects_oversized_query(client: TestClient) -> None:
    tokens = register_user(client, email="long@example.com")
    response = client.post(
        "/api/v1/articles",
        json={"query": "x" * 3000},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_generation_failure_returns_error_not_fake_content(
    client: TestClient,
) -> None:
    from app.ai.factory import get_provider

    get_provider().permanent_failure = True

    tokens = register_user(client, email="fail@example.com")
    response = client.post(
        "/api/v1/articles",
        json={"query": "topics that will fail"},
        headers=auth_headers(tokens["access_token"]),
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "GENERATION_FAILED"

    # No half-created articles survive a failed generation.
    listing = client.get("/api/v1/articles", headers=auth_headers(tokens["access_token"]))
    assert listing.json()["items"] == []


def test_transient_provider_failure_is_retried(client: TestClient) -> None:
    from app.ai.factory import get_provider

    get_provider().transient_failures_remaining = 1

    tokens = register_user(client, email="retry@example.com")
    detail = generate_article(client, tokens["access_token"])
    assert detail["current_version"] == 1


def test_list_articles_cursor_pagination(client: TestClient) -> None:
    tokens = register_user(client, email="page@example.com")
    headers = auth_headers(tokens["access_token"])
    for i in range(3):
        generate_article(client, tokens["access_token"], query=f"Topic number {i}")

    page1 = client.get("/api/v1/articles?limit=2", headers=headers).json()
    assert len(page1["items"]) == 2
    assert page1["next_cursor"]

    page2 = client.get(
        f"/api/v1/articles?limit=2&cursor={page1['next_cursor']}", headers=headers
    ).json()
    assert len(page2["items"]) == 1
    assert page2["next_cursor"] is None
    ids = [a["id"] for a in page1["items"] + page2["items"]]
    assert len(set(ids)) == 3


def test_get_article_requires_ownership(client: TestClient) -> None:
    owner = register_user(client, email="owner@example.com")
    detail = generate_article(client, owner["access_token"])

    intruder = register_user(client, email="intruder@example.com")

    ok = client.get(
        f"/api/v1/articles/{detail['id']}", headers=auth_headers(owner["access_token"])
    )
    assert ok.status_code == 200

    for method, path in [
        ("GET", f"/api/v1/articles/{detail['id']}"),
        ("PATCH", f"/api/v1/articles/{detail['id']}"),
        ("DELETE", f"/api/v1/articles/{detail['id']}"),
        ("POST", f"/api/v1/articles/{detail['id']}/rewrite"),
        ("GET", f"/api/v1/articles/{detail['id']}/versions"),
    ]:
        kwargs = (
            {"json": {"title": "Hacked"}}
            if method == "PATCH"
            else ({"json": {"style": "genz"}} if method == "POST" else {})
        )
        response = getattr(client, method.lower())(
            path, headers=auth_headers(intruder["access_token"]), **kwargs
        )
        assert response.status_code == 404, f"{method} {path} leaked data"


def test_get_missing_article_returns_404_envelope(client: TestClient) -> None:
    tokens = register_user(client, email="missing@example.com")
    response = client.get(
        "/api/v1/articles/9999", headers=auth_headers(tokens["access_token"])
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_rename_and_delete_article(client: TestClient) -> None:
    tokens = register_user(client, email="lifecycle@example.com")
    headers = auth_headers(tokens["access_token"])
    detail = generate_article(client, tokens["access_token"])

    renamed = client.patch(
        f"/api/v1/articles/{detail['id']}", json={"title": "My Renamed Title"}, headers=headers
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "My Renamed Title"

    deleted = client.delete(f"/api/v1/articles/{detail['id']}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/articles/{detail['id']}", headers=headers).status_code == 404


def test_duplicate_article(client: TestClient) -> None:
    tokens = register_user(client, email="dup-article@example.com")
    headers = auth_headers(tokens["access_token"])
    detail = generate_article(client, tokens["access_token"])

    copy = client.post(f"/api/v1/articles/{detail['id']}/duplicate", headers=headers)
    assert copy.status_code == 201
    body = copy.json()
    assert body["id"] != detail["id"]
    assert body["title"].endswith("(copy)")
    assert body["current_version"] == 1
    assert body["seo"] == detail["seo"]


def test_rewrite_creates_new_version(client: TestClient) -> None:
    tokens = register_user(client, email="rewrite@example.com")
    headers = auth_headers(tokens["access_token"])
    detail = generate_article(client, tokens["access_token"])

    rewritten = client.post(
        f"/api/v1/articles/{detail['id']}/rewrite",
        json={"style": "genz"},
        headers=headers,
    )
    assert rewritten.status_code == 200
    assert rewritten.json()["current_version"] == 2

    versions = client.get(f"/api/v1/articles/{detail['id']}/versions", headers=headers).json()
    assert [v["version"] for v in versions["items"]] == [2, 1]
    assert versions["items"][0]["change_type"] == "rewrite"


def test_rewrite_rejects_unknown_style(client: TestClient) -> None:
    tokens = register_user(client, email="badstyle@example.com")
    detail = generate_article(client, tokens["access_token"])

    response = client.post(
        f"/api/v1/articles/{detail['id']}/rewrite",
        json={"style": "shakespearean"},
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNKNOWN_STYLE"


def test_restore_version(client: TestClient) -> None:
    tokens = register_user(client, email="restore@example.com")
    headers = auth_headers(tokens["access_token"])
    detail = generate_article(client, tokens["access_token"])
    article_id = detail["id"]

    client.post(
        f"/api/v1/articles/{article_id}/rewrite", json={"style": "minimal"}, headers=headers
    )

    restored = client.post(
        f"/api/v1/articles/{article_id}/versions/1/restore", headers=headers
    )
    assert restored.status_code == 200
    assert restored.json()["current_version"] == 3

    versions = client.get(f"/api/v1/articles/{article_id}/versions", headers=headers).json()
    assert [v["change_type"] for v in versions["items"]] == ["restore", "rewrite", "generation"]

    v1 = client.get(f"/api/v1/articles/{article_id}/versions/1", headers=headers)
    assert v1.status_code == 200
    assert v1.json()["markdown"].startswith("# ")


def test_rewrite_styles_endpoint(client: TestClient) -> None:
    tokens = register_user(client, email="styles@example.com")
    styles = client.get(
        "/api/v1/articles/rewrite-styles", headers=auth_headers(tokens["access_token"])
    )
    assert styles.status_code == 200
    keys = [s["key"] for s in styles.json()["styles"]]
    assert "genz" in keys and "professional" in keys


def test_generation_endpoints_rate_limited(client: TestClient) -> None:
    tokens = register_user(client, email="ratelimit@example.com")
    headers = auth_headers(tokens["access_token"])

    statuses = []
    for _ in range(7):
        response = client.post(
            "/api/v1/articles", json={"query": "rate limit test"}, headers=headers
        )
        statuses.append(response.status_code)

    assert 429 in statuses
    assert statuses[-1] == 429
