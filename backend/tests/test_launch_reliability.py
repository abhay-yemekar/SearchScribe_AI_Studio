"""Regression coverage for the audited publishing and persistence boundaries."""

import pytest
from conftest import auth_headers, generate_article, register_user
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.prompts import render_prompt
from app.db.models import Article
from app.repositories.article_repo import ArticleRepository


def test_prompt_preserves_plain_text() -> None:
    topic = 'Best "cheap" trips & <tips>'
    assert topic in render_prompt("article_generation", "v1", {"topic": topic})


def test_rendered_robots_and_docs_policy(client: TestClient) -> None:
    token = register_user(client)["access_token"]
    article = generate_article(client, token)
    assert '<meta name="robots" content="index, follow">' in article["html"]
    assert "https://cdn.jsdelivr.net" in client.get("/docs").headers["content-security-policy"]
    assert "https://cdn.jsdelivr.net" not in client.get(
        "/api/v1/health"
    ).headers["content-security-policy"]


@pytest.mark.parametrize("length,status", [(2, 422), (3, 201), (500, 201), (501, 422)])
def test_query_boundaries(client: TestClient, length: int, status: int) -> None:
    token = register_user(client)["access_token"]
    response = client.post("/api/v1/articles", json={"query": "x" * length},
                           headers=auth_headers(token))
    assert response.status_code == status


@pytest.mark.parametrize("cursor", ["abc", "-1", "0", "", "9" * 30])
def test_invalid_cursor_is_client_error(client: TestClient, cursor: str) -> None:
    token = register_user(client)["access_token"]
    response = client.get("/api/v1/articles", params={"cursor": cursor},
                          headers=auth_headers(token))
    assert response.status_code == 400


def test_full_final_page_has_no_cursor(client: TestClient) -> None:
    token = register_user(client)["access_token"]
    generate_article(client, token)
    response = client.get("/api/v1/articles?limit=1", headers=auth_headers(token))
    assert response.json()["next_cursor"] is None


def test_generation_rolls_back_after_version_write(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = register_user(client)["access_token"]

    def fail_seo(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Injected persistence failure")

    monkeypatch.setattr(ArticleRepository, "set_seo", fail_seo)
    with pytest.raises(RuntimeError, match="Injected persistence failure"):
        generate_article(client, token)
    assert db_session.scalar(select(func.count()).select_from(Article)) == 0
