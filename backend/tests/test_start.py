"""A failed migration must never expose the HTTP server."""

from __future__ import annotations

import subprocess
import sys
from unittest.mock import patch

import pytest

from app.start import main


def test_start_migrates_before_serving_render_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "10000")
    with patch("app.start.subprocess.run") as migrate, patch("app.start.uvicorn.run") as serve:
        main()
    migrate.assert_called_once_with(
        [sys.executable, "-m", "alembic", "upgrade", "head"], check=True
    )
    serve.assert_called_once_with(
        "app.main:app", host="0.0.0.0", port=10000, proxy_headers=False  # noqa: S104
    )


def test_failed_migration_prevents_server_start() -> None:
    with (
        patch("app.start.subprocess.run", side_effect=subprocess.CalledProcessError(1, "alembic")),
        patch("app.start.uvicorn.run") as serve,
        pytest.raises(subprocess.CalledProcessError),
    ):
        main()
    serve.assert_not_called()


@pytest.mark.parametrize("port", ["0", "65536", "not-a-port"])
def test_invalid_port_fails_before_migration(
    port: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORT", port)
    with patch("app.start.subprocess.run") as migrate, pytest.raises(ValueError):
        main()
    migrate.assert_not_called()
