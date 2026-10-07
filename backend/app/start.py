"""Single-instance hosting entrypoint: migrate successfully before serving."""

from __future__ import annotations

import os
import subprocess
import sys

import uvicorn


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    # One worker: the current rate limiter is process-local. Keep proxy headers
    # disabled until a trusted ingress is configured; never trust arbitrary XFF.
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, proxy_headers=False)  # noqa: S104


if __name__ == "__main__":
    main()
