"""Recovery secrets, session revocation, shared limits and atomic token consumption."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

import jwt
import pytest
from conftest import TEST_PASSWORD, auth_headers, register_user
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.exceptions import AuthenticationError, BadRequestError
from app.core.rate_limit import limiter
from app.db.base import Base, utc_now
from app.db.models import ProviderIdentity, RefreshToken, SecurityRateBucket, SecurityToken, User
from app.db.session import create_db_engine
from app.services.account_recovery import AccountRecoveryService, hash_security_token
from app.services.auth_service import AuthService
from app.services.google_auth import google_user
from app.services.transactional_mail import MailDeliveryError

FORGOT = "/api/v1/auth/password/forgot"
RESET = "/api/v1/auth/password/reset"
REQUEST_VERIFY = "/api/v1/auth/email/verification/request"
VERIFY = "/api/v1/auth/email/verify"
NEW_PASSWORD = "new-correct-horse-2"


@pytest.fixture
def security_mail(monkeypatch):
    monkeypatch.setattr(settings, "mail_provider", "brevo")
    monkeypatch.setattr(settings, "security_email_requests_per_hour", 10)
    monkeypatch.setattr(settings, "security_ip_requests_per_hour", 100)
    with patch("app.services.account_recovery.send_security_email") as sender:
        yield sender


def sent_code(sender, kind):
    return next(
        call.kwargs["token"] for call in reversed(sender.call_args_list) if call.args[0] == kind
    )


def request_reset(client, sender, email="user@example.com"):
    assert client.post(FORGOT, json={"email": email}).status_code == 202
    return sent_code(sender, "password_reset")


def test_signup_verification_is_advisory_and_one_use(client, security_mail, db_session):
    account = register_user(client)
    assert account["user"]["email_verified"] is False
    headers = auth_headers(account["access_token"])
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    code = sent_code(security_mail, "email_verification")
    assert client.post(VERIFY, json={"token": code}).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).json()["email_verified"] is True
    assert client.post(VERIFY, json={"token": code}).status_code == 400
    before = security_mail.call_count
    assert client.post(REQUEST_VERIFY, headers=headers).status_code == 202
    assert security_mail.call_count == before
    stored = db_session.scalar(select(SecurityToken))
    assert stored.token_hash == hash_security_token(code)
    assert stored.token_hash != code
    assert stored.consumed_at is not None


def test_reset_revokes_all_sessions_and_requires_new_login(client, security_mail, db_session):
    first = register_user(client)
    first_refresh = client.cookies.get("ss_refresh_token")
    second = client.post(
        "/api/v1/auth/login", json={"email": "user@example.com", "password": TEST_PASSWORD}
    ).json()
    second_refresh = client.cookies.get("ss_refresh_token")
    code = request_reset(client, security_mail)
    result = client.post(RESET, json={"token": code, "password": NEW_PASSWORD})
    assert result.status_code == 200
    assert "access_token" not in result.json()
    assert client.cookies.get("ss_refresh_token") is None
    for account in (first, second):
        assert (
            client.get("/api/v1/auth/me", headers=auth_headers(account["access_token"])).status_code
            == 401
        )
    for refresh in (first_refresh, second_refresh):
        client.cookies.set("ss_refresh_token", refresh)
        assert client.post("/api/v1/auth/refresh").status_code == 401
    assert (
        client.post(RESET, json={"token": code, "password": "another-password-3"}).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "user@example.com", "password": TEST_PASSWORD}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "user@example.com", "password": NEW_PASSWORD}
        ).status_code
        == 200
    )
    user = db_session.scalar(select(User))
    assert user.session_version == 1
    assert all(token.revoked_at for token in db_session.scalars(select(RefreshToken)).all()[:-1])
    assert any(
        call.args[0] == "password_changed" and call.kwargs["token"] is None
        for call in security_mail.call_args_list
    )


def test_forgot_is_neutral_for_unknown_disabled_and_google_only(client, security_mail, db_session):
    register_user(client)
    db_session.add_all(
        [
            User(
                email="google@example.com", name="Google", password_hash=None, email_verified=True
            ),
            User(
                email="disabled@example.com",
                name="Disabled",
                password_hash="unused",
                is_active=False,
            ),
        ]
    )
    db_session.commit()
    responses = []
    for email in (
        "user@example.com",
        "unknown@example.com",
        "google@example.com",
        "disabled@example.com",
    ):
        responses.append(client.post(FORGOT, json={"email": email}))
    assert {response.status_code for response in responses} == {202}
    assert all(response.json() == responses[0].json() for response in responses)
    assert all(response.headers["cache-control"] == "no-store" for response in responses)
    assert (
        len([call for call in security_mail.call_args_list if call.args[0] == "password_reset"])
        == 1
    )
    assert (
        db_session.scalar(select(User).where(User.email == "google@example.com")).password_hash
        is None
    )


def test_mail_delivery_failure_never_changes_neutral_response_or_signup(
    client, security_mail, caplog
):
    security_mail.side_effect = MailDeliveryError("secret-provider-error-email@example.com")
    assert register_user(client)["user"]["email_verified"] is False
    known = client.post(FORGOT, json={"email": "user@example.com"})
    missing = client.post(FORGOT, json={"email": "absent@example.com"})
    assert known.status_code == missing.status_code == 202
    assert known.json() == missing.json()
    assert "secret-provider-error" not in caplog.text


@pytest.mark.parametrize(
    "purpose,path", [("password_reset", RESET), ("email_verification", VERIFY)]
)
def test_expired_security_code_is_rejected(client, security_mail, db_session, purpose, path):
    register_user(client)
    code = (
        request_reset(client, security_mail)
        if purpose == "password_reset"
        else sent_code(security_mail, purpose)
    )
    stored = db_session.scalar(
        select(SecurityToken).where(SecurityToken.token_hash == hash_security_token(code))
    )
    stored.expires_at = utc_now() - timedelta(seconds=1)
    db_session.commit()
    payload = {"token": code, "password": NEW_PASSWORD} if path == RESET else {"token": code}
    assert client.post(path, json=payload).status_code == 400
    assert stored.consumed_at is None


def test_tokens_are_purpose_bound_and_reset_invalidates_other_codes(client, security_mail):
    register_user(client)
    verify_code = sent_code(security_mail, "email_verification")
    first_code = request_reset(client, security_mail)
    second_code = request_reset(client, security_mail)
    assert (
        client.post(RESET, json={"token": verify_code, "password": NEW_PASSWORD}).status_code == 400
    )
    assert client.post(VERIFY, json={"token": first_code}).status_code == 400
    assert (
        client.post(RESET, json={"token": first_code, "password": NEW_PASSWORD}).status_code == 200
    )
    assert (
        client.post(RESET, json={"token": second_code, "password": NEW_PASSWORD}).status_code == 400
    )
    assert client.post(VERIFY, json={"token": verify_code}).status_code == 400


def test_password_strength_and_authenticated_verification_request(client, security_mail):
    assert client.post(REQUEST_VERIFY).status_code == 401
    register_user(client)
    code = request_reset(client, security_mail)
    assert client.post(RESET, json={"token": code, "password": "weakpass"}).status_code == 422
    assert client.post(RESET, json={"token": code, "password": NEW_PASSWORD}).status_code == 200


def test_persistent_email_and_ip_limits_are_neutral_and_ignore_spoofed_headers(
    client, security_mail, monkeypatch, db_session
):
    register_user(client)
    security_mail.reset_mock()
    monkeypatch.setattr(settings, "security_email_requests_per_hour", 2)
    monkeypatch.setattr(settings, "security_ip_requests_per_hour", 3)
    first = client.post(FORGOT, json={"email": "user@example.com"})
    limiter.reset()  # A process-memory reset cannot reset the persistent budget.
    second = client.post(FORGOT, json={"email": "user@example.com"})
    third = client.post(
        FORGOT, json={"email": "new@example.com"}, headers={"x-forwarded-for": "198.51.100.8"}
    )
    fourth = client.post(
        FORGOT, json={"email": "user@example.com"}, headers={"x-forwarded-for": "198.51.100.9"}
    )
    assert all(
        response.status_code == 202 and response.json() == first.json()
        for response in (second, third, fourth)
    )
    # Signup already spent one request. Only the first reset request can send.
    assert security_mail.call_count == 1
    keys = [bucket.key for bucket in db_session.scalars(select(SecurityRateBucket))]
    assert all("example.com" not in key and "testclient" not in key for key in keys)


def test_verification_preserves_recovery_reserve_and_total_cap(client, security_mail, monkeypatch):
    monkeypatch.setattr(settings, "mail_daily_limit", 3)
    monkeypatch.setattr(settings, "mail_recovery_reserve", 1)
    account = register_user(client)
    headers = auth_headers(account["access_token"])
    assert client.post(REQUEST_VERIFY, headers=headers).status_code == 202
    assert client.post(REQUEST_VERIFY, headers=headers).status_code == 202
    assert security_mail.call_count == 2
    code = request_reset(client, security_mail)
    assert security_mail.call_count == 3
    assert client.post(RESET, json={"token": code, "password": NEW_PASSWORD}).status_code == 200
    # Password change still succeeds when its courtesy notice has no reservation.
    assert security_mail.call_count == 3


def test_disabled_provider_has_neutral_response_without_tokens(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "mail_provider", "disabled")
    register_user(client)
    known = client.post(FORGOT, json={"email": "user@example.com"})
    missing = client.post(FORGOT, json={"email": "absent@example.com"})
    assert known.status_code == missing.status_code == 202
    assert known.json() == missing.json()
    assert db_session.scalar(select(SecurityToken)) is None


def test_legacy_access_token_valid_until_reset(client, security_mail):
    account = register_user(client)
    legacy = jwt.encode(
        {
            "sub": str(account["user"]["id"]),
            "type": "access",
            "exp": utc_now() + timedelta(minutes=5),
        },
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    assert client.get("/api/v1/auth/me", headers=auth_headers(legacy)).status_code == 200
    code = request_reset(client, security_mail)
    assert client.post(RESET, json={"token": code, "password": NEW_PASSWORD}).status_code == 200
    assert client.get("/api/v1/auth/me", headers=auth_headers(legacy)).status_code == 401


@pytest.fixture
def concurrent_factory(db_engine, tmp_path):
    # CI's PostgreSQL matrix exercises real row locks. Local concurrency needs
    # separate SQLite connections, unlike the normal StaticPool test fixture.
    engine = db_engine
    if engine.dialect.name == "sqlite":
        engine = create_db_engine(f"sqlite:///{tmp_path / 'concurrency.db'}")
        Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    if engine is not db_engine:
        engine.dispose()


def seed_reset(factory):
    with factory() as db:
        user = AuthService(db).signup(email="race@example.com", name="Race", password=TEST_PASSWORD)
        session = AuthService(db).issue_session(user)
        mail = AccountRecoveryService(db).request_password_reset(user.email, "seed")
        return user.id, session, mail.token


def test_concurrent_reset_consumes_code_once(concurrent_factory, security_mail):
    _, _, code = seed_reset(concurrent_factory)
    barrier = Barrier(2)

    def reset(index):
        with concurrent_factory() as db:
            barrier.wait(timeout=10)
            try:
                AccountRecoveryService(db).reset_password(
                    code, f"replacement-pass-{index}", f"ip-{index}"
                )
                return "success"
            except BadRequestError:
                return "invalid"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reset, (1, 2))) == ["invalid", "success"]
    with concurrent_factory() as db:
        assert db.scalar(select(User.session_version)) == 1


def test_old_password_login_cannot_issue_session_after_reset(concurrent_factory, security_mail):
    _, _, code = seed_reset(concurrent_factory)
    with concurrent_factory() as stale_db:
        stale = AuthService(stale_db).login(email="race@example.com", password=TEST_PASSWORD)
        with concurrent_factory() as reset_db:
            AccountRecoveryService(reset_db).reset_password(code, NEW_PASSWORD, "reset")
        with pytest.raises(AuthenticationError):
            AuthService(stale_db).issue_session(stale)


def test_stale_refresh_cannot_resurrect_session_after_reset(concurrent_factory, security_mail):
    _, session, code = seed_reset(concurrent_factory)
    from app.core.security import hash_refresh_token

    with concurrent_factory() as stale_db:
        stale = stale_db.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(session.refresh_token)
            )
        )
        assert stale.revoked_at is None
        with concurrent_factory() as reset_db:
            AccountRecoveryService(reset_db).reset_password(code, NEW_PASSWORD, "reset")
        with pytest.raises(AuthenticationError):
            AuthService(stale_db).rotate_refresh_session(session.refresh_token)
    with concurrent_factory() as db:
        assert all(token.revoked_at is not None for token in db.scalars(select(RefreshToken)))


def test_concurrent_daily_reservation_never_exceeds_cap(
    concurrent_factory, security_mail, monkeypatch
):
    monkeypatch.setattr(settings, "mail_daily_limit", 3)
    monkeypatch.setattr(settings, "mail_recovery_reserve", 1)
    with concurrent_factory() as db:
        service = AccountRecoveryService(db)
        assert service._reserve_mail("password_reset")
        assert service._reserve_mail("password_reset")
        db.commit()
    barrier = Barrier(2)

    def reserve(_index):
        with concurrent_factory() as db:
            barrier.wait(timeout=10)
            allowed = AccountRecoveryService(db)._reserve_mail("password_reset")
            db.commit()
            return allowed

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reserve, (1, 2))) == [False, True]
    with concurrent_factory() as db:
        assert db.scalar(select(SecurityRateBucket.count)) == 3


def test_stale_authenticated_google_link_is_rejected_after_reset(
    concurrent_factory,
    security_mail,
):
    user_id, _, code = seed_reset(concurrent_factory)
    with concurrent_factory() as stale_db:
        stale = stale_db.get(User, user_id)
        with concurrent_factory() as reset_db:
            AccountRecoveryService(reset_db).reset_password(code, NEW_PASSWORD, "reset")
        with pytest.raises(AuthenticationError):
            google_user(
                stale_db,
                {"sub": "stale-google", "email": "race@example.com"},
                current=stale,
                password=TEST_PASSWORD,
            )
    with concurrent_factory() as db:
        assert db.scalar(select(ProviderIdentity)) is None


def test_google_only_account_cannot_reset_even_with_inserted_security_token(
    client,
    db_session,
    security_mail,
):
    code = "unusable-password-reset-code-32"
    user = User(email="google@example.com", name="Google", password_hash=None, email_verified=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(
        SecurityToken(
            user_id=user.id,
            purpose="password_reset",
            token_hash=hash_security_token(code),
            session_version=0,
            expires_at=utc_now() + timedelta(minutes=10),
        )
    )
    db_session.commit()
    assert client.post(RESET, json={"token": code, "password": NEW_PASSWORD}).status_code == 400
    db_session.refresh(user)
    assert user.password_hash is None


def test_google_claim_verifies_only_matching_stored_email(db_session):
    user = User(
        email="original@example.com", name="Google", password_hash=None, email_verified=False
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(ProviderIdentity(user_id=user.id, provider="google", subject="existing-google"))
    db_session.commit()
    returned = google_user(db_session, {"sub": "existing-google", "email": "changed@example.com"})
    assert returned.id == user.id
    assert returned.email_verified is False
    returned = google_user(db_session, {"sub": "existing-google", "email": "original@example.com"})
    assert returned.email_verified is True
