"""Versioned editor and optimistic concurrency coverage."""

from conftest import auth_headers, generate_article, register_user
from fastapi.testclient import TestClient


def _edit_payload(detail: dict, *, title: str, seo_title: str) -> dict:
    content = {**detail["content"], "title": title}
    seo = {**detail["seo"], "title": seo_title}
    return {"base_version": detail["current_version"], "content": content, "seo": seo}


def test_edit_creates_complete_version(client: TestClient) -> None:
    session = register_user(client, email="editor@example.com")
    headers = auth_headers(session["access_token"])
    article = generate_article(client, session["access_token"])

    response = client.put(
        f"/api/v1/articles/{article['id']}/content",
        json=_edit_payload(article, title="Edited title", seo_title="Edited SEO title"),
        headers=headers,
    )

    assert response.status_code == 200
    edited = response.json()
    assert edited["current_version"] == 2
    assert edited["title"] == "Edited title"
    assert edited["seo"]["title"] == "Edited SEO title"
    versions = client.get(f"/api/v1/articles/{article['id']}/versions", headers=headers).json()[
        "items"
    ]
    assert versions[0]["change_type"] == "edit"
    assert versions[0]["complete_snapshot"] is True


def test_stale_edit_returns_current_version(client: TestClient) -> None:
    session = register_user(client, email="stale-editor@example.com")
    headers = auth_headers(session["access_token"])
    article = generate_article(client, session["access_token"])
    payload = _edit_payload(article, title="First edit", seo_title="First SEO")
    assert (
        client.put(
            f"/api/v1/articles/{article['id']}/content", json=payload, headers=headers
        ).status_code
        == 200
    )

    stale = client.put(f"/api/v1/articles/{article['id']}/content", json=payload, headers=headers)
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "STALE_ARTICLE_VERSION"
    assert stale.json()["error"]["details"]["current_version"] == 2


def test_restore_restores_seo_snapshot(client: TestClient) -> None:
    session = register_user(client, email="restore-seo@example.com")
    headers = auth_headers(session["access_token"])
    article = generate_article(client, session["access_token"])
    original_seo = article["seo"]["title"]
    edited = client.put(
        f"/api/v1/articles/{article['id']}/content",
        json=_edit_payload(article, title="New title", seo_title="New SEO"),
        headers=headers,
    )
    assert edited.status_code == 200

    restored = client.post(f"/api/v1/articles/{article['id']}/versions/1/restore", headers=headers)
    assert restored.status_code == 200
    assert restored.json()["seo"]["title"] == original_seo


def test_editor_rejects_unsafe_canonical_url(client: TestClient) -> None:
    session = register_user(client, email="canonical@example.com")
    article = generate_article(client, session["access_token"])
    payload = _edit_payload(article, title="Safe title", seo_title="Safe SEO")
    payload["seo"]["canonical_url"] = "javascript:alert(1)"
    response = client.put(
        f"/api/v1/articles/{article['id']}/content",
        json=payload,
        headers=auth_headers(session["access_token"]),
    )
    assert response.status_code == 422
