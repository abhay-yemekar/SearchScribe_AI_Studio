"""Authentication endpoints: signup, login, refresh, logout, me."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.exceptions import AuthenticationError
from ...core.rate_limit import rate_limit
from ...db.models import User
from ...db.session import get_db
from ...schemas.auth import (
    ForgotPasswordRequest,
    GoogleLinkRequest,
    GoogleRequest,
    LoginRequest,
    MessageOut,
    ResetPasswordRequest,
    SecurityTokenRequest,
    SignupRequest,
    TokenOut,
    UserOut,
)
from ...services.account_recovery import (
    FORGOT_MESSAGE,
    VERIFICATION_MESSAGE,
    AccountRecoveryService,
    deliver_security_email,
)
from ...services.auth_service import AuthService, SessionTokens
from ...services.google_auth import google_user, new_challenge, verify_google
from ..deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "ss_refresh_token"
GOOGLE_COOKIE_NAME = "ss_google_challenge"


@router.get(
    "/google/challenge",
    dependencies=[rate_limit("google_challenge", settings.rate_limit_auth_per_minute)],
)
def google_challenge(response: Response) -> dict[str, str | bool]:
    response.headers["Cache-Control"] = "no-store"
    if not settings.google_client_id:
        return {"enabled": False}
    nonce, signed = new_challenge()
    response.set_cookie(
        GOOGLE_COOKIE_NAME,
        signed,
        max_age=300,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        path="/api/v1/auth/google",
    )
    return {"enabled": True, "client_id": settings.google_client_id, "nonce": nonce}


@router.post(
    "/google",
    response_model=TokenOut,
    dependencies=[rate_limit("auth", settings.rate_limit_auth_per_minute)],
)
def google_login(
    payload: GoogleRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> TokenOut:
    claims = verify_google(payload.credential, request.cookies.get(GOOGLE_COOKIE_NAME))
    user = google_user(db, claims)
    tokens = AuthService(db).issue_session(user)
    _set_refresh_cookie(response, tokens.refresh_token)
    response.delete_cookie(GOOGLE_COOKIE_NAME, path="/api/v1/auth/google")
    return _token_payload(user, tokens)


@router.post("/google/link", dependencies=[rate_limit("auth", settings.rate_limit_auth_per_minute)])
def google_link(
    payload: GoogleLinkRequest,
    request: Request,
    response: Response,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    claims = verify_google(payload.credential, request.cookies.get(GOOGLE_COOKIE_NAME))
    google_user(db, claims, current=current, password=payload.password)
    response.delete_cookie(GOOGLE_COOKIE_NAME, path="/api/v1/auth/google")
    return {"linked": True}


@router.get("/connections")
def connections(current: User = Depends(get_current_user)) -> dict[str, bool]:
    return {
        "password": bool(current.password_hash),
        "google": any(identity.provider == "google" for identity in current.identities),
    }


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
def signup(
    payload: SignupRequest, request: Request, response: Response,
    background_tasks: BackgroundTasks, db: Session = Depends(get_db),
) -> TokenOut:
    service = AuthService(db)
    user = service.signup(email=payload.email, name=payload.name, password=payload.password)
    tokens = service.issue_session(user)
    _set_refresh_cookie(response, tokens.refresh_token)
    message = AccountRecoveryService(db).request_verification(user, _client_ip(request))
    if message is not None:
        background_tasks.add_task(deliver_security_email, message)
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


def _client_ip(request: Request) -> str:
    # Trust the ASGI client's address, never raw user-supplied forwarding headers.
    return request.client.host if request.client else "unknown"


@router.post("/password/forgot", response_model=MessageOut, status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
    payload: ForgotPasswordRequest, request: Request, response: Response,
    background_tasks: BackgroundTasks, db: Session = Depends(get_db),
) -> MessageOut:
    response.headers["Cache-Control"] = "no-store"
    message = AccountRecoveryService(db).request_password_reset(payload.email, _client_ip(request))
    if message is not None:
        background_tasks.add_task(deliver_security_email, message)
    return MessageOut(message=FORGOT_MESSAGE)


@router.post("/password/reset", response_model=MessageOut)
def reset_password(
    payload: ResetPasswordRequest, request: Request, response: Response,
    background_tasks: BackgroundTasks, db: Session = Depends(get_db),
) -> MessageOut:
    response.headers["Cache-Control"] = "no-store"
    message = AccountRecoveryService(db).reset_password(
        payload.token, payload.password, _client_ip(request),
    )
    if message is not None:
        background_tasks.add_task(deliver_security_email, message)
    _clear_refresh_cookie(response)
    return MessageOut(message="Password updated. Sign in again with your new password.")


@router.post(
    "/email/verification/request", response_model=MessageOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_email_verification(
    request: Request, response: Response, background_tasks: BackgroundTasks,
    current: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> MessageOut:
    response.headers["Cache-Control"] = "no-store"
    message = AccountRecoveryService(db).request_verification(current, _client_ip(request))
    if message is not None:
        background_tasks.add_task(deliver_security_email, message)
    return MessageOut(message=VERIFICATION_MESSAGE)


@router.post("/email/verify", response_model=MessageOut)
def verify_email(
    payload: SecurityTokenRequest, request: Request, response: Response,
    db: Session = Depends(get_db),
) -> MessageOut:
    response.headers["Cache-Control"] = "no-store"
    AccountRecoveryService(db).verify_email(payload.token, _client_ip(request))
    return MessageOut(message="Email verified. You can return to your account.")
