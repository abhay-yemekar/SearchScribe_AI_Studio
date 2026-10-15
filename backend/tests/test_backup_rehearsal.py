"""Refusal boundaries and functional acceptance for the disposable CI rehearsal."""

import pytest

from app.core.rate_limit import limiter
from scripts.backup_rehearsal import guarded_database_url, main, seed, verify_api


@pytest.mark.parametrize("url", [
    "postgresql+psycopg://searchscribe:x@neon.example:5432/searchscribe_backup_test",
    "postgresql+psycopg://searchscribe:x@localhost:5432/production",
    "postgresql+psycopg://office:x@localhost:5432/searchscribe_backup_test",
    "postgresql+psycopg://searchscribe:x@localhost:5433/searchscribe_backup_test",
    "postgresql+psycopg://searchscribe:x@localhost:5432/searchscribe_backup_test?host=remote",
    "postgresql+psycopg://searchscribe:x@localhost:5432/searchscribe_restore_test",
    "sqlite:///searchscribe.db",
])
def test_refuses_unapproved_database_without_connecting(url):
    with pytest.raises(ValueError):
        guarded_database_url(url, "seed")


def test_requires_distinct_seed_and_restore_databases():
    source = "postgresql+psycopg://searchscribe:x@localhost:5432/searchscribe_backup_test"
    target = "postgresql+psycopg://searchscribe:x@localhost:5432/searchscribe_restore_test"
    assert guarded_database_url(source, "seed") == source
    assert guarded_database_url(target, "verify") == target
    with pytest.raises(ValueError):
        guarded_database_url(source, "verify")


def test_rehearsal_api_checks_versions_credits_ownership_journals_and_new_inserts(client):
    manifest = seed(client)
    limiter.reset()  # Each CLI stage runs in a fresh process in the CI rehearsal.
    verify_api(client, manifest)
    limiter.reset()
    verify_api(client, manifest, rollback=True)


@pytest.mark.parametrize("setting,value", [("APP_ENV", "production"), ("AI_PROVIDER", "gemini"),
                                          ("BACKUP_REHEARSAL", "0")])
def test_cli_refuses_non_test_runs_before_loading_app(monkeypatch, tmp_path, setting, value):
    import sys

    for name, default in (("APP_ENV", "test"), ("AI_PROVIDER", "mock"), ("BACKUP_REHEARSAL", "1")):
        monkeypatch.setenv(name, default)
    monkeypatch.setenv(setting, value)
    evidence = tmp_path / "evidence.json"
    monkeypatch.setattr(sys, "argv", ["rehearsal", "seed", "--evidence", str(evidence)])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert not evidence.exists()


def test_changed_article_is_not_accepted(client):
    manifest = seed(client)
    limiter.reset()
    manifest["article_sha256"] = "0" * 64
    with pytest.raises(AssertionError, match="Article/export content changed"):
        verify_api(client, manifest)
