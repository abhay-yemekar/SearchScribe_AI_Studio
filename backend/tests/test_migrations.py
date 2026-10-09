"""Alembic migrations produce the expected schema from scratch."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command

BACKEND_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_TABLES = {
    "users",
    "refresh_tokens",
    "articles",
    "article_versions",
    "seo_metadata",
    "generations",
    "alembic_version",
    "provider_identities",
    "security_tokens",
    "security_rate_buckets",
}


def _alembic_config(db_url: str) -> Config:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_upgrade_head_creates_all_tables(tmp_path: object) -> None:
    db_path = Path(str(tmp_path)) / "mig.db"
    db_url = f"sqlite:///{db_path}"

    command.upgrade(_alembic_config(db_url), "head")

    engine = create_engine(db_url)
    tables = set(inspect(engine).get_table_names())
    assert tables >= EXPECTED_TABLES


def test_downgrade_base_drops_all_tables(tmp_path: object) -> None:
    db_path = Path(str(tmp_path)) / "mig.db"
    db_url = f"sqlite:///{db_path}"
    cfg = _alembic_config(db_url)

    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    engine = create_engine(db_url)
    tables = set(inspect(engine).get_table_names())
    assert tables == {"alembic_version"} or EXPECTED_TABLES.isdisjoint(tables)


def test_postgres_offline_migrations_preserve_encoded_password() -> None:
    output = StringIO()
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"), output_buffer=output)
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    url = "postgresql://writer:p%40ss%25word@localhost/searchscribe_test?sslmode=require"
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(cfg, "head", sql=True)
    assert "CREATE TABLE users" in output.getvalue()
    assert cfg.get_main_option("sqlalchemy.url") == url.replace(
        "postgresql://", "postgresql+psycopg://"
    )


def test_google_upgrade_preserves_existing_users_and_articles(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'existing.db'}"
    cfg = _alembic_config(db_url)
    command.upgrade(cfg, "a84f2e510c7b")
    engine = create_engine(db_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id,email,name,password_hash,is_active,created_at,updated_at) "
                "VALUES (1,'old@example.com','Old','hash',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO articles (id,user_id,title,query,status,created_at,updated_at) "
                "VALUES (1,1,'Old draft','Old topic','draft',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        )
    command.upgrade(cfg, "head")
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT password_hash FROM users WHERE id=1")).scalar()
            == "hash"
        )
        assert (
            connection.execute(text("SELECT title FROM articles WHERE id=1")).scalar()
            == "Old draft"
        )
    command.downgrade(cfg, "a84f2e510c7b")


def test_security_email_upgrade_preserves_legacy_accounts_sessions_and_articles(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'security-existing.db'}"
    cfg = _alembic_config(db_url)
    command.upgrade(cfg, "b91e_google_identities")
    engine = create_engine(db_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id,email,name,password_hash,is_active,created_at,updated_at) "
                "VALUES (1,'old@example.com','Old','hash',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP), "
                "(2,'google@example.com','Google',NULL,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO provider_identities (user_id,provider,subject) "
                "VALUES (2,'google','known-sub')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO refresh_tokens (user_id,token_hash,expires_at,created_at) "
                "VALUES (1,'old-session-hash','2099-01-01',CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO articles (id,user_id,title,query,status,created_at,updated_at) "
                "VALUES (1,1,'Existing draft','Old topic','draft',"
                "CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        )
    command.upgrade(cfg, "head")
    with engine.connect() as connection:
        password_account = connection.execute(
            text("SELECT password_hash,email_verified,session_version FROM users WHERE id=1")
        ).one()
        assert tuple(password_account) == ("hash", 0, 0)
        google_account = connection.execute(
            text("SELECT password_hash,email_verified,session_version FROM users WHERE id=2")
        ).one()
        assert tuple(google_account) == (None, 1, 0)
        assert connection.execute(
            text("SELECT token_hash,session_version FROM refresh_tokens")
        ).one() == ("old-session-hash", 0)
        assert connection.execute(text("SELECT title FROM articles")).scalar() == "Existing draft"
        assert connection.execute(text("SELECT COUNT(*) FROM security_tokens")).scalar() == 0
    command.downgrade(cfg, "b91e_google_identities")
    assert "email_verified" not in {
        column["name"] for column in inspect(engine).get_columns("users")
    }
