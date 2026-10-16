"""Persistent fixed-window abuse counters stored in ``security_rate_buckets``.

Unlike the in-memory minute limiter these survive restarts and are shared by
every worker. Keys are HMACs, so rows never reveal email addresses or IPs.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ..core.config import settings
from ..db.models import SecurityRateBucket


def _bucket_key(scope: str, value: str, start: datetime) -> str:
    return hmac.new(
        settings.secret_key.encode(),
        f"{scope}:{value}:{start.isoformat()}".encode(),
        hashlib.sha256,
    ).hexdigest()


def take_bucket(
    db: Session, scope: str, value: str, start: datetime, end: datetime, limit: int
) -> bool:
    """Atomically count one use; False once this window already holds ``limit``."""
    dialect = db.get_bind().dialect.name
    insert = postgres_insert if dialect == "postgresql" else sqlite_insert
    stmt = insert(SecurityRateBucket).values(
        key=_bucket_key(scope, value, start), count=1, expires_at=end
    )
    reserved = db.scalar(
        stmt.on_conflict_do_update(
            index_elements=[SecurityRateBucket.key],
            set_={"count": SecurityRateBucket.count + 1},
            where=SecurityRateBucket.count < limit,
        ).returning(SecurityRateBucket.count)
    )
    return reserved is not None


def clear_bucket(db: Session, scope: str, value: str, start: datetime) -> None:
    db.execute(
        delete(SecurityRateBucket).where(
            SecurityRateBucket.key == _bucket_key(scope, value, start)
        )
    )


def delete_expired_buckets(db: Session, now: datetime) -> None:
    db.execute(delete(SecurityRateBucket).where(SecurityRateBucket.expires_at < now))
