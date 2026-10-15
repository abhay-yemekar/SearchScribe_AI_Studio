"""Reserve before AI work; complete the journal in the article's transaction.

An ambiguous/interrupted request is never automatically sent to a provider again.
The same user/key may only identify one payload, even across process restarts.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.exceptions import (
    AppError,
    BadRequestError,
    ConflictError,
    NotFoundError,
    RateLimitError,
)
from ..db.base import utc_now
from ..db.models.operation import GenerationBudget, GenerationOperation

_CONTEXT_KEY = "generation_operation_id"


def complete_operation(db: Session, article_id: int, version: int) -> None:
    """Called immediately before committing the article/version, never afterward."""
    operation_id = db.info.get(_CONTEXT_KEY)
    if operation_id is None:
        return
    completed = db.scalar(
        update(GenerationOperation)
        .where(GenerationOperation.id == operation_id,
               GenerationOperation.status == "processing",
               GenerationOperation.deadline_at > utc_now())
        .values(status="completed", article_id=article_id, result_version=version,
                finished_at=utc_now())
        .returning(GenerationOperation.id)
    )
    if completed is None:
        raise ConflictError("This generation request expired. Your saved work is unchanged.",
                            code="GENERATION_INTERRUPTED")


class OperationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def run(
        self, user_id: int, key: str | None, kind: str,
        payload: dict[str, object], action: Callable[[], int],
    ) -> tuple[int, str]:
        operation, fresh = self.reserve(user_id, key, kind, payload)
        if not fresh:
            if operation.article_id is None:
                raise ConflictError("The original article was deleted. No new draft was generated.",
                                    code="GENERATION_RESULT_REMOVED")
            return operation.article_id, operation.request_key
        operation_id, accepted_key = operation.id, operation.request_key
        try:
            article_id = action()
            return article_id, accepted_key
        except IntegrityError as exc:
            self.failed(operation_id, "STALE_ARTICLE_VERSION")
            raise ConflictError("The article changed while generating. Reload the latest version.",
                                code="STALE_ARTICLE_VERSION") from exc
        except AppError as exc:
            self.failed(operation_id, exc.code)
            raise
        except Exception:
            self.failed(operation_id, "INTERNAL_ERROR")
            raise
        finally:
            self.clear_context()

    def find(self, user_id: int, key: str) -> GenerationOperation:
        operation = self.db.scalar(select(GenerationOperation).where(
            GenerationOperation.user_id == user_id, GenerationOperation.request_key == key,
        ))
        if operation is None:
            raise NotFoundError("Generation request not found.")
        if operation.status == "processing" and operation.deadline_at <= utc_now():
            self.db.execute(update(GenerationOperation).where(
                GenerationOperation.id == operation.id,
                GenerationOperation.status == "processing",
            ).values(status="interrupted", error_code="GENERATION_INTERRUPTED",
                     finished_at=utc_now()))
            self.db.commit()
            self.db.refresh(operation)
        return operation

    def reserve(
        self, user_id: int, key: str | None, kind: str, payload: dict[str, object],
    ) -> tuple[GenerationOperation, bool]:
        key = key if key is not None else uuid4().hex
        if not re.fullmatch(r"[A-Za-z0-9_-]{16,64}", key):
            raise BadRequestError("Use a 16-64 character request key.", code="INVALID_REQUEST_KEY")
        fingerprint = hashlib.sha256(json.dumps(
            {"kind": kind, **payload}, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        now = utc_now()
        insert = (postgres_insert if self.db.get_bind().dialect.name == "postgresql"
                  else sqlite_insert)
        operation_id = self.db.scalar(insert(GenerationOperation).values(
            user_id=user_id, request_key=key, kind=kind, fingerprint=fingerprint,
            status="processing", created_at=now,
            deadline_at=now + timedelta(seconds=settings.ai_operation_timeout_seconds + 30),
        ).on_conflict_do_nothing(index_elements=["user_id", "request_key"])
          .returning(GenerationOperation.id))
        if operation_id is None:
            self.db.rollback()
            previous = self.find(user_id, key)
            if previous.fingerprint != fingerprint:
                raise ConflictError("This request key belongs to a different topic or action.",
                                    code="REQUEST_KEY_REUSED")
            if previous.status == "completed":
                return previous, False
            code = {"processing": "GENERATION_IN_PROGRESS", "failed": "GENERATION_FAILED",
                    "interrupted": "GENERATION_INTERRUPTED"}[previous.status]
            raise ConflictError(
                "This request is still running. Check its status before starting another."
                if previous.status == "processing" else
                "This request did not complete. Check your workspace before trying a new request.",
                code=code,
            )

        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        self.db.execute(delete(GenerationBudget).where(GenerationBudget.expires_at <= now))
        # Every worker acquires global then user, in the same transaction/order.
        for scope, limit in (
            ("global", settings.generation_daily_global_limit),
            (f"user:{user_id}", settings.generation_daily_user_limit),
        ):
            bucket = f"{start.date().isoformat()}:{scope}"
            taken = self.db.scalar(insert(GenerationBudget).values(
                key=bucket, count=1, expires_at=end,
            ).on_conflict_do_update(index_elements=["key"],
                set_={"count": GenerationBudget.count + 1}, where=GenerationBudget.count < limit,
            ).returning(GenerationBudget.count))
            if taken is None:
                self.db.rollback()  # Also releases the other bucket and journal insertion.
                raise RateLimitError(
                    "The daily generation limit has been reached. "
                    "Editing and exports are available.",
                    code="GENERATION_DAILY_LIMIT",
                    details={"retry_after_seconds": max(1, int((end - now).total_seconds())),
                             "reset_at": end.isoformat() + "Z",
                             "retry_at": end.isoformat() + "Z"},
                )
        self.db.commit()
        self.db.info[_CONTEXT_KEY] = operation_id
        operation = self.db.get(GenerationOperation, operation_id)
        assert operation is not None
        return operation, True

    def failed(self, operation_id: int, code: str) -> None:
        self.db.rollback()
        self.db.execute(update(GenerationOperation).where(
            GenerationOperation.id == operation_id,
            GenerationOperation.status == "processing",
        ).values(status="interrupted" if code == "GENERATION_INTERRUPTED" else "failed",
                 error_code=code[:60], finished_at=utc_now()))
        self.db.commit()

    def clear_context(self) -> None:
        self.db.info.pop(_CONTEXT_KEY, None)
