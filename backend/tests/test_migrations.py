"""Alembic migrations produce the expected schema from scratch."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

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
