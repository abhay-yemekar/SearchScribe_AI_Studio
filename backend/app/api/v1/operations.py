"""Authenticated recovery lookup; never restarts an ambiguous provider request."""

from typing import Literal

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...db.models import User
from ...db.session import get_db
from ...services.operation_service import OperationService
from ..deps import get_current_user

router = APIRouter(prefix="/generation-requests", tags=["articles"])


class OperationOut(BaseModel):
    request_key: str
    kind: str
    status: Literal["processing", "completed", "failed", "interrupted"]
    article_id: int | None
    result_version: int | None
    error_code: str | None
    deadline_at: str


@router.get("/{request_key}", response_model=OperationOut)
def get_operation(
    request_key: str = Path(pattern=r"^[A-Za-z0-9_-]{16,64}$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OperationOut:
    operation = OperationService(db).find(current_user.id, request_key)
    return OperationOut(
        request_key=operation.request_key, kind=operation.kind, status=operation.status,
        article_id=operation.article_id, result_version=operation.result_version,
        error_code=operation.error_code, deadline_at=operation.deadline_at.isoformat() + "Z",
    )
