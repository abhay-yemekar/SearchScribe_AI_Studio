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
