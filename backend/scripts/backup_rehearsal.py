"""Synthetic PostgreSQL restore acceptance; deliberately refuses remote databases."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, select, text
from sqlalchemy.engine import Engine, make_url

PASSWORD = "rehearsal-only-password-1"  # noqa: S105
OWNER = "backup-owner@example.com"
OTHER = "backup-other@example.com"
QUERY = "A practical guide to balcony gardens"
REQUEST_KEY = "backup-rehearsal-generation-0001"
FAILED_KEY = "backup-rehearsal-failed-00000001"


def guarded_database_url(value: str, stage: str) -> str:
    """These exact disposable databases are the only permitted rehearsal targets."""
    url = make_url(value)
    database = "searchscribe_backup_test" if stage == "seed" else "searchscribe_restore_test"
    if (url.drivername != "postgresql+psycopg"
            or url.host not in {"localhost", "127.0.0.1", "postgres"}
            or url.port != 5432 or url.database != database
            or url.username != "searchscribe" or url.query):
        raise ValueError("Rehearsal requires the named disposable local PostgreSQL database")
    return value


def digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def database_snapshot(engine: Engine) -> dict[str, Any]:
    """Compare every table/column/row, without writing their contents to evidence."""
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        metadata = MetaData()
        metadata.reflect(bind=connection)
        result = {}
        for table in metadata.sorted_tables:
            rows = [digest(dict(row)) for row in connection.execute(select(table)).mappings()]
            result[table.name] = {
                "columns": [{"name": column.name, "type": str(column.type),
                             "nullable": column.nullable, "primary_key": column.primary_key}
                            for column in table.columns],
                "rows": len(rows), "sha256": digest(sorted(rows)),
            }
        return result


def expect(response: Any, status: int) -> dict[str, Any]:
    if response.status_code != status:
        raise AssertionError(f"{response.request.method} API response: expected {status}, "
                             f"received {response.status_code}")
    return response.json()


def login(client: Any, email: str) -> dict[str, str]:
    tokens = expect(client.post("/api/v1/auth/login", json={
        "email": email, "password": PASSWORD,
    }), 200)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def article_digest(article: dict[str, Any]) -> str:
    return digest({key: article[key] for key in (
        "id", "title", "query", "status", "current_version", "content", "seo", "html", "markdown",
    )})


def seed(client: Any) -> dict[str, Any]:
    """Create only fictional accounts; exercise the real API, snapshots and journals."""
    from app.ai.factory import get_provider
    from app.schemas.media import PhotoAsset
    from app.services.photo_service import selection_token

    users = []
    for email in (OWNER, OTHER):
        tokens = expect(client.post("/api/v1/auth/signup", json={
            "name": "Backup Rehearsal", "email": email, "password": PASSWORD,
        }), 201)
        users.append(tokens["user"]["id"])
    headers = login(client, OWNER)
    article = expect(client.post("/api/v1/articles", json={"query": QUERY}, headers={
        **headers, "Idempotency-Key": REQUEST_KEY,
    }), 201)
    article_id = article["id"]
    asset = PhotoAsset(
        source_id=123, title="Rehearsal.jpg", creator="Fictional Rehearsal Photographer",
        source_url="https://commons.wikimedia.org/wiki/File:Rehearsal.jpg",
        preview_url="https://upload.wikimedia.org/wikipedia/commons/a/ab/Rehearsal.jpg",
        original_url="https://upload.wikimedia.org/wikipedia/commons/a/ab/Rehearsal.jpg",
        license_name="CC BY 4.0", license_url="https://creativecommons.org/licenses/by/4.0/",
        width=4096, height=2730,
    )
    article = expect(client.put(f"/api/v1/articles/{article_id}/photos", headers=headers, json={
        "base_version": 1, "photos": [{
            "selection_token": selection_token(asset, users[0], article_id),
            "alt": "A fictional balcony garden — café & herbs",
        }],
    }), 200)
    article["content"]["title"] = "Balcony notes — café & gardens"
    article["seo"]["title"] = "A practical balcony garden"
    article["seo"]["description"] = "Plan a small balcony garden with space for herbs and rest."
    article = expect(client.put(f"/api/v1/articles/{article_id}/content", headers=headers, json={
        "base_version": 2, "content": article["content"], "seo": article["seo"],
    }), 200)
    expect(client.post(f"/api/v1/articles/{article_id}/rewrite", headers={
        **headers, "Idempotency-Key": "backup-rehearsal-rewrite-0000001",
    }, json={"style": "genz"}), 200)
    article = expect(client.post(
        f"/api/v1/articles/{article_id}/versions/3/restore", headers=headers,
    ), 200)
    other = expect(client.post("/api/v1/articles", json={"query": "Private fictional notes"},
                               headers=login(client, OTHER)), 201)
    provider = get_provider()
    provider.permanent_failure = True
    try:
        expect(client.post("/api/v1/articles", json={"query": "Fictional failed request"},
                           headers={**headers, "Idempotency-Key": FAILED_KEY}), 502)
    finally:
        provider.permanent_failure = False
    versions = expect(client.get(f"/api/v1/articles/{article_id}/versions", headers=headers), 200)
    version_digests = {
        str(version["version"]): digest(expect(client.get(
            f"/api/v1/articles/{article_id}/versions/{version['version']}", headers=headers,
        ), 200)) for version in versions["items"]
    }
    assert article["current_version"] == 5
    assert len(article["content"]["photos"]) == 1
    return {
        "article_id": article_id, "other_article_id": other["id"],
        "max_user_id": max(users), "max_article_id": max(article_id, other["id"]),
        "article_sha256": article_digest(article), "versions": version_digests,
    }


def verify_api(client: Any, manifest: dict[str, Any], *, rollback: bool = False) -> None:
    headers, other_headers = login(client, OWNER), login(client, OTHER)
    article_id = manifest["article_id"]
    article = expect(client.get(f"/api/v1/articles/{article_id}", headers=headers), 200)
    assert article_digest(article) == manifest["article_sha256"], "Article/export content changed"
    for version, expected in manifest["versions"].items():
        actual = expect(client.get(f"/api/v1/articles/{article_id}/versions/{version}",
                                   headers=headers), 200)
        assert digest(actual) == expected, f"Version {version} changed"
    for path in (f"/api/v1/articles/{article_id}",
                 f"/api/v1/articles/{article_id}/versions",
                 f"/api/v1/articles/{article_id}/versions/3"):
        assert client.get(path, headers=other_headers).status_code == 404
    assert client.patch(f"/api/v1/articles/{article_id}", headers=other_headers,
                        json={"title": "Unauthorized change"}).status_code == 404
    assert client.get(f"/api/v1/articles/{manifest['other_article_id']}",
                      headers=headers).status_code == 404
    # The previous application may predate journals. Its rollback acceptance is
    # reading/exporting existing work; generation must stay suspended operationally.
    if rollback:
        return
    status = expect(client.get(f"/api/v1/generation-requests/{REQUEST_KEY}", headers=headers), 200)
    assert status["status"] == "completed" and status["article_id"] == article_id
    failed = expect(client.get(f"/api/v1/generation-requests/{FAILED_KEY}", headers=headers), 200)
    assert failed["status"] == "failed" and failed["error_code"] == "GENERATION_FAILED"
    assert client.get(f"/api/v1/generation-requests/{REQUEST_KEY}",
                      headers=other_headers).status_code == 404
    from app.ai.factory import get_provider

    provider = get_provider()
    provider.permanent_failure = True
    try:
        replay = expect(client.post("/api/v1/articles", json={"query": QUERY}, headers={
            **headers, "Idempotency-Key": REQUEST_KEY,
        }), 201)
        assert article_digest(replay) == manifest["article_sha256"]
    finally:
        provider.permanent_failure = False
    # Inserts after restore catch sequence state errors, not just copied row counts.
    tokens = expect(client.post("/api/v1/auth/signup", json={
        "name": "After Restore", "email": "after-restore@example.com", "password": PASSWORD,
    }), 201)
    assert tokens["user"]["id"] > manifest["max_user_id"]
    new_article = expect(client.post("/api/v1/articles", json={"query": "After restore notes"},
                                    headers=login(client, "after-restore@example.com")), 201)
    assert new_article["id"] > manifest["max_article_id"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("seed", "verify", "rollback"))
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--app-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    if (os.environ.get("BACKUP_REHEARSAL") != "1" or os.environ.get("APP_ENV") != "test"
            or os.environ.get("AI_PROVIDER") != "mock"):
        parser.error("Explicit BACKUP_REHEARSAL=1, APP_ENV=test and AI_PROVIDER=mock are required")
    url = guarded_database_url(os.environ.get("BACKUP_REHEARSAL_DATABASE_URL", ""), args.stage)
    os.environ.update({
        "DATABASE_URL": url, "SECRET_KEY": "backup-rehearsal-only-signing-key",
        "MAIL_PROVIDER": "disabled", "BREVO_API_KEY": "", "GOOGLE_CLIENT_ID": "",
        "GEMINI_API_KEY": "", "GROQ_API_KEY": "", "TAVILY_API_KEY": "",
        "PHOTO_PROVIDER": "disabled", "DRAFT_REVIEW_ENABLED": "false",
        "AI_FALLBACK_PROVIDER": "", "AI_FALLBACK_MODEL": "",
        "RESEARCH_PLANNER_PROVIDER": "", "RESEARCH_PLANNER_MODEL": "",
        "RESEARCH_PLANNER_FALLBACK_PROVIDER": "", "RESEARCH_PLANNER_FALLBACK_MODEL": "",
        "RESEARCH_REVIEWER_PROVIDER": "", "RESEARCH_REVIEWER_MODEL": "",
        "DRAFT_REVIEWER_PROVIDER": "", "DRAFT_REVIEWER_MODEL": "",
        "GENERATION_DAILY_USER_LIMIT": "100", "GENERATION_DAILY_GLOBAL_LIMIT": "1000",
        "RATE_LIMIT_AUTH_PER_MINUTE": "100", "RATE_LIMIT_GENERATION_PER_MINUTE": "100",
    })
    app_root = args.app_root.resolve(strict=True)
    sys.path.insert(0, str(app_root))
    from fastapi.testclient import TestClient

    from app.db.session import engine
    from app.main import app

    if args.stage == "seed":
        from alembic.config import Config

        from alembic import command

        if database_snapshot(engine):
            raise RuntimeError("Seed database must be empty; no data will be overwritten")
        config = Config(str(app_root / "alembic.ini"))
        config.set_main_option("script_location", str(app_root / "alembic"))
        config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
        command.upgrade(config, "head")
        with TestClient(app) as client:
            manifest = seed(client)
        manifest["tables"] = database_snapshot(engine)
        with engine.connect() as connection:
            manifest["schema_revision"] = connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
            manifest["postgres_version"] = connection.scalar(text("SHOW server_version"))
        manifest["acceptance"] = {"seed": "passed"}
        manifest["seed_code"] = os.environ.get("GITHUB_SHA", "local")
    else:
        manifest = json.loads(args.evidence.read_text(encoding="utf-8"))
        if args.stage == "verify":
            assert database_snapshot(engine) == manifest["tables"], "Restored rows/schema differ"
        with TestClient(app) as client:
            verify_api(client, manifest, rollback=args.stage == "rollback")
        manifest["acceptance"][args.stage] = "passed"
        if args.stage == "rollback":
            manifest["previous_code"] = os.environ.get("REHEARSAL_ROLLBACK_SHA", "local")
    args.evidence.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"stage": args.stage, "result": "passed",
                      "schema_revision": manifest["schema_revision"]}))
    engine.dispose()


if __name__ == "__main__":
    main()
