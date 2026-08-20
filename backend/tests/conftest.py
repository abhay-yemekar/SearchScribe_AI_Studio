"""Test bootstrap: configure environment before the app is imported."""

from __future__ import annotations

import os
import tempfile

# Isolated SQLite file per test session (created before app import so that
# engine construction in app.db.session picks it up).
_TMP_DB = os.path.join(tempfile.mkdtemp(prefix="searchscribe-test-"), "test.db")

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP_DB}")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("AI_PROVIDER", "mock")
os.environ.setdefault("GEMINI_API_KEY", "")
