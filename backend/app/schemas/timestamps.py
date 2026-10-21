"""Timestamps in API responses are explicit UTC."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from pydantic import PlainSerializer


def _utc_iso(value: datetime) -> str:
    # Stored times are naive UTC (db.base.utc_now). Without an offset, browsers
    # read them as local time, so version times were hours off outside UTC.
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


UtcDateTime = Annotated[datetime, PlainSerializer(_utc_iso, return_type=str, when_used="json")]
