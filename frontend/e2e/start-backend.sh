#!/usr/bin/env bash
# Starts the E2E backend: throwaway SQLite DB, mock AI provider, port 8001.
set -euo pipefail

cd "$(dirname "$0")/../../backend"

rm -f e2e_test.db

export DATABASE_URL="sqlite:///./e2e_test.db"
export AI_PROVIDER="mock"
export SECRET_KEY="e2e-local-only-not-production-0123456789"
export GEMINI_API_KEY=""
export CORS_ORIGINS="http://127.0.0.1:3100,http://localhost:3100"
export RATE_LIMIT_AUTH_PER_MINUTE="120"
export RATE_LIMIT_GENERATION_PER_MINUTE="120"

PY="${E2E_PYTHON:-../.venv/Scripts/python}"
if ! command -v "$PY" >/dev/null 2>&1; then
  PY="../.venv/bin/python"
fi

"$PY" -m alembic upgrade head
exec "$PY" -m uvicorn app.main:app --port 8001 --log-level warning
