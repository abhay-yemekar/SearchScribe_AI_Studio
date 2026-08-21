"""Authentication endpoints: signup, login, refresh, logout, me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.exceptions import AuthenticationError
from ...core.rate_limit import rate_limit
from ...db.models import User
from ...db.session import get_db
from ...schemas.auth import LoginRequest, SignupRequest, TokenOut, UserOut
from ...services.auth_service import AuthService, SessionTokens
from ..deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "ss_refresh_token"


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_token,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        # Only ever needed by /auth/refresh and /auth/logout.
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/api/v1/auth")


def _token_payload(user: User, tokens: SessionTokens) -> TokenOut:
    return TokenOut(
        access_token=tokens.access_token,
        expires_in=tokens.expires_in,
        user=UserOut.model_validate(user),
    )


@router.post(
    "/signup",
    response_model=TokenOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account and start a session",
    dependencies=[rate_limit("auth", settings.rate_limit_auth_per_minute)],
)
def signup(payload: SignupRequest, response: Response, db: Session = Depends(get_db)) -> TokenOut:
    service = AuthService(db)
    user = service.signup(
        email=payload.email, name=payload.name, password=payload.password
    )
    tokens = service.issue_session(user)
    _set_refresh_cookie(response, tokens.refresh_token)
    return _token_payload(user, tokens)


@router.post(
    "/login",
    response_model=TokenOut,
    summary="Exchange credentials for an access token + refresh cookie",
    dependencies=[rate_limit("auth", settings.rate_limit_auth_per_minute)],
)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> TokenOut:
    service = AuthService(db)
    user = service.login(email=payload.email, password=payload.password)
    tokens = service.issue_session(user)
    _set_refresh_cookie(response, tokens.refresh_token)
    return _token_payload(user, tokens)


@router.post(
    "/refresh",
    response_model=TokenOut,
    summary="Rotate the refresh cookie and issue a new access token",
    dependencies=[rate_limit("auth", settings.rate_limit_auth_per_minute)],
)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> TokenOut:
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_token:
        raise AuthenticationError("Missing session cookie.")
    service = AuthService(db)
    user, tokens = service.rotate_refresh_session(raw_token)
    _set_refresh_cookie(response, tokens.refresh_token)
    return _token_payload(user, tokens)


@router.post(
    "/logout",
    summary="Revoke the current session",
)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, bool]:
    service = AuthService(db)
    service.logout(request.cookies.get(REFRESH_COOKIE_NAME))
    _clear_refresh_cookie(response)
    return {"ok": True}


@router.get(
    "/me",
    response_model=UserOut,
    summary="Current authenticated user",
)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)
