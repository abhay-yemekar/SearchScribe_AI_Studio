"""Use the installed psycopg driver for hosting-provider Postgres URLs."""

from sqlalchemy.engine import make_url


def normalize_database_url(value: str) -> str:
    try:
        url = make_url(value)
    except Exception:
        # Do not echo a connection string (which can contain a password).
        raise ValueError("DATABASE_URL must be a valid SQLAlchemy connection URL") from None
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    return url.render_as_string(hide_password=False)
