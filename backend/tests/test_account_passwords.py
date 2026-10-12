"""Password management preserves identity and requires fresh, bounded authorization."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

import jwt
import pytest
from conftest import TEST_PASSWORD, auth_headers, generate_article, register_user
from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.exceptions import AuthenticationError
from app.core.rate_limit import limiter
from app.db.base import Base, utc_now
from app.db.models import ProviderIdentity, RefreshToken, SecurityToken, User
from app.db.session import create_db_engine
from app.services.account_passwords import PASSWORD_ADD_AUDIENCE, AccountPasswordService
from app.services.account_recovery import hash_security_token
from app.services.auth_service import AuthService
from app.services.google_auth import new_challenge
from app.services.transactional_mail import MailDeliveryError

ADD = "/api/v1/auth/password/add"
CHALLENGE = ADD + "/challenge"
CHANGE = "/api/v1/auth/password/change"
COOKIE = "ss_password_add_challenge"
NEW_PASSWORD = "new-correct-horse-2"


@pytest.fixture(autouse=True)
def password_settings(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "test-client.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "mail_provider", "brevo")
    monkeypatch.setattr(settings, "security_email_requests_per_hour", 50)
    monkeypatch.setattr(settings, "security_ip_requests_per_hour", 100)
    with patch("app.services.account_recovery.send_security_email") as sender:
        yield sender


def google_account(client, subject="owner-sub", email="google@example.com"):
    challenge = client.get("/api/v1/auth/google/challenge").json()
    with patch(
        "app.services.google_auth.id_token.verify_oauth2_token",
        return_value={
            "sub": subject,
            "email": email,
            "email_verified": True,
            "name": "Google writer",
            "nonce": challenge["nonce"],
        },
    ):
        result = client.post("/api/v1/auth/google", json={"credential": "test-id-token"})
    assert result.status_code == 200, result.text
    return result.json()


def submit_add(client, account, nonce, subject="owner-sub", email="google@example.com"):
    with patch(
        "app.services.google_auth.id_token.verify_oauth2_token",
        return_value={
            "sub": subject,
            "email": email,
            "email_verified": True,
            "nonce": nonce,
        },
    ):
        return client.post(
            ADD,
            json={"credential": "test-id-token", "password": NEW_PASSWORD},
            headers=auth_headers(account["access_token"]),
        )


def challenge(client, account):
    response = client.get(CHALLENGE, headers=auth_headers(account["access_token"]))
    assert response.status_code == 200, response.text
    return response.json()["nonce"]


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("get", CHALLENGE, None),
        ("post", ADD, {"credential": "test", "password": NEW_PASSWORD}),
        ("post", CHANGE, {"current_password": TEST_PASSWORD, "password": NEW_PASSWORD}),
    ],
)
def test_password_management_requires_authenticated_session(client, method, path, payload):
    assert (
        getattr(client, method)(path, **({"json": payload} if payload else {})).status_code == 401
    )


def test_add_challenge_is_private_and_hashed(client, db_session, monkeypatch):
    account = google_account(client)
    response = client.get(CHALLENGE, headers=auth_headers(account["access_token"]))
    assert response.headers["cache-control"] == "no-store"
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Max-Age=300" in cookie and "SameSite=strict" in cookie
    assert "Path=/api/v1/auth/password/add" in cookie
    stored = db_session.scalar(select(SecurityToken).where(SecurityToken.purpose == "password_add"))
    nonce = response.json()["nonce"]
    assert stored.token_hash == hash_security_token(nonce) and stored.token_hash != nonce
    assert stored.session_version == 0 and stored.user_id == account["user"]["id"]
    monkeypatch.setattr(settings, "google_client_id", "")
    disabled = client.get(CHALLENGE, headers=auth_headers(account["access_token"]))
    assert disabled.json() == {"enabled": False}
    assert disabled.headers["cache-control"] == "no-store"


def test_add_keeps_articles_and_google_identity_but_revokes_sessions(
    client,
    db_session,
    password_settings,
):
    account = google_account(client)
    article = generate_article(client, account["access_token"])
    old_refresh = client.cookies.get("ss_refresh_token")
    nonce = challenge(client, account)
    client.get("/api/v1/auth/google/challenge")
    # An outstanding unrelated verification token must also become unusable.
    db_session.add(
        SecurityToken(
            user_id=account["user"]["id"],
            purpose="email_verification",
            token_hash=hash_security_token("pending-email-verification-code"),
            session_version=0,
            expires_at=utc_now() + timedelta(hours=1),
        )
    )
    db_session.commit()
    result = submit_add(client, account, nonce)
    assert result.status_code == 200 and "access_token" not in result.json()
    assert result.headers["cache-control"] == "no-store"
    assert all(
        client.cookies.get(name) is None
        for name in (COOKIE, "ss_refresh_token", "ss_google_challenge")
    )
    assert (
        client.get("/api/v1/auth/me", headers=auth_headers(account["access_token"])).status_code
        == 401
    )
    client.cookies.set("ss_refresh_token", old_refresh)
    assert client.post("/api/v1/auth/refresh").status_code == 401
    signed_in = client.post(
        "/api/v1/auth/login",
        json={
            "email": "google@example.com",
            "password": NEW_PASSWORD,
        },
    )
    assert signed_in.status_code == 200
    assert signed_in.json()["user"]["id"] == account["user"]["id"]
    new_headers = auth_headers(signed_in.json()["access_token"])
    assert client.get(f"/api/v1/articles/{article['id']}", headers=new_headers).status_code == 200
    assert client.get("/api/v1/auth/connections", headers=new_headers).json() == {
        "google": True,
        "password": True,
    }
    assert google_account(client)["user"]["id"] == account["user"]["id"]
    db_session.expire_all()
    assert db_session.get(User, account["user"]["id"]).session_version == 1
    assert db_session.scalar(select(ProviderIdentity)).subject == "owner-sub"
    assert all(token.consumed_at for token in db_session.scalars(select(SecurityToken)))
    assert password_settings.call_args.args[0] == "password_added"
    assert password_settings.call_args.kwargs["token"] is None


def test_wrong_google_sub_cannot_add_even_with_same_email(client, db_session):
    account = google_account(client)
    nonce = challenge(client, account)
    wrong = submit_add(client, account, nonce, subject="attacker-sub")
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "PASSWORD_GOOGLE_VERIFICATION_FAILED"
    db_session.expire_all()
    assert db_session.get(User, account["user"]["id"]).password_hash is None
    assert submit_add(client, account, nonce).status_code == 200


def test_linked_sub_can_reauthenticate_after_google_email_changes(client):
    account = google_account(client)
    assert (
        submit_add(
            client, account, challenge(client, account), email="renamed@example.com"
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={
                "email": "google@example.com",
                "password": NEW_PASSWORD,
            },
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "mode", ["missing", "ordinary", "expired", "tampered", "wrong_user", "wrong_version"]
)
def test_add_rejects_missing_wrong_purpose_expired_or_unbound_cookie(client, mode):
    account = google_account(client)
    nonce = challenge(client, account)
    client.cookies.clear()
    if mode == "ordinary":
        _, signed = new_challenge()
    else:
        signed = jwt.encode(
            {
                "aud": PASSWORD_ADD_AUDIENCE,
                "nonce": nonce,
                "uid": account["user"]["id"] + (1 if mode == "wrong_user" else 0),
                "sv": 1 if mode == "wrong_version" else 0,
                "exp": 1 if mode == "expired" else utc_now() + timedelta(minutes=5),
            },
            settings.secret_key,
            algorithm="HS256",
        )
    if mode != "missing":
        client.cookies.set(COOKIE, signed + ("tampered" if mode == "tampered" else ""))
    with patch("app.services.google_auth.id_token.verify_oauth2_token") as verifier:
        assert (
            client.post(
                ADD,
                json={"credential": "test", "password": NEW_PASSWORD},
                headers=auth_headers(account["access_token"]),
            ).status_code
            == 401
        )
        verifier.assert_not_called()


def test_ordinary_google_nonce_cannot_authorize_add(client):
    account = google_account(client)
    nonce = challenge(client, account)
    ordinary = client.get("/api/v1/auth/google/challenge").json()["nonce"]
    assert submit_add(client, account, ordinary).status_code == 401
    assert submit_add(client, account, nonce).status_code == 200


def test_only_latest_persistent_add_challenge_can_be_used(client, db_session):
    account = google_account(client)
    first_nonce = challenge(client, account)
    first_cookie = client.cookies.get(COOKIE)
    second_nonce = challenge(client, account)
    second_cookie = client.cookies.get(COOKIE)
    client.cookies.clear()
    client.cookies.set(COOKIE, first_cookie)
    assert submit_add(client, account, first_nonce).status_code == 401
    client.cookies.clear()
    client.cookies.set(COOKIE, second_cookie)
    assert submit_add(client, account, second_nonce).status_code == 200
    assert submit_add(client, account, second_nonce).status_code == 401
    db_session.expire_all()
    assert len(db_session.scalars(select(SecurityToken)).all()) == 2
    assert all(token.consumed_at for token in db_session.scalars(select(SecurityToken)))


@pytest.mark.parametrize("state", ["expired", "consumed", "wrong_purpose", "wrong_version"])
def test_add_challenge_database_state_is_enforced(client, db_session, state):
    account = google_account(client)
    nonce = challenge(client, account)
    token = db_session.scalar(select(SecurityToken))
    if state == "expired":
        token.expires_at = utc_now() - timedelta(seconds=1)
    elif state == "consumed":
        token.consumed_at = utc_now()
    elif state == "wrong_purpose":
        token.purpose = "password_reset"
    else:
        token.session_version = 1
    db_session.commit()
    assert submit_add(client, account, nonce).status_code == 401


def test_add_challenge_requires_google_only_account(client, db_session):
    password_account = register_user(client)
    assert (
        client.get(CHALLENGE, headers=auth_headers(password_account["access_token"])).status_code
        == 409
    )
    user = User(email="unlinked@example.com", name="Unlinked", password_hash=None)
    db_session.add(user)
    db_session.commit()
    tokens = AuthService(db_session).issue_session(user)
    assert client.get(CHALLENGE, headers=auth_headers(tokens.access_token)).status_code == 409


@pytest.mark.parametrize("path", [ADD, CHANGE])
@pytest.mark.parametrize("password", ["short1", "onlyletters", "12345678", "x" * 129 + "1"])
def test_management_uses_existing_password_rules(client, path, password):
    account = google_account(client) if path == ADD else register_user(client)
    body = (
        {"password": password, "credential": "test"}
        if path == ADD
        else {
            "password": password,
            "current_password": TEST_PASSWORD,
        }
    )
    assert (
        client.post(path, json=body, headers=auth_headers(account["access_token"])).status_code
        == 422
    )


def test_change_requires_current_password_and_invalidates_all_security_tokens(
    client,
    db_session,
    password_settings,
):
    account = register_user(client)
    headers = auth_headers(account["access_token"])
    old_refresh = client.cookies.get("ss_refresh_token")
    wrong = client.post(
        CHANGE,
        json={"current_password": "incorrect", "password": NEW_PASSWORD},
        headers=headers,
    )
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "PASSWORD_CURRENT_INVALID"
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    client.get("/api/v1/auth/google/challenge")
    client.cookies.set(COOKIE, "old-password-challenge", domain="testserver.local", path=ADD)
    result = client.post(
        CHANGE, json={"current_password": TEST_PASSWORD, "password": NEW_PASSWORD}, headers=headers
    )
    assert result.status_code == 200 and result.headers["cache-control"] == "no-store"
    assert all(
        client.cookies.get(name) is None
        for name in (COOKIE, "ss_refresh_token", "ss_google_challenge")
    )
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    client.cookies.set("ss_refresh_token", old_refresh)
    assert client.post("/api/v1/auth/refresh").status_code == 401
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
    db_session.expire_all()
    assert db_session.get(User, account["user"]["id"]).session_version == 1
    assert all(token.consumed_at for token in db_session.scalars(select(SecurityToken)))
    assert all(token.revoked_at for token in db_session.scalars(select(RefreshToken)).all()[:-1])
    assert password_settings.call_args.args[0] == "password_changed"


def test_google_only_account_cannot_change_password(client):
    account = google_account(client)
    assert (
        client.post(
            CHANGE,
            json={"current_password": TEST_PASSWORD, "password": NEW_PASSWORD},
            headers=auth_headers(account["access_token"]),
        ).status_code
        == 401
    )


@pytest.mark.parametrize("mutation", ["disabled", "version"])
def test_disabled_or_stale_account_cannot_add(client, db_session, mutation):
    account = google_account(client)
    nonce = challenge(client, account)
    user = db_session.get(User, account["user"]["id"])
    if mutation == "disabled":
        user.is_active = False
    else:
        user.session_version += 1
    db_session.commit()
    assert submit_add(client, account, nonce).status_code == 401


def test_password_management_limits_persist_across_process_limiter_reset(client, monkeypatch):
    account = google_account(client)
    monkeypatch.setattr(settings, "security_email_requests_per_hour", 2)
    challenge(client, account)
    limiter.reset()
    challenge(client, account)
    limiter.reset()
    assert client.get(CHALLENGE, headers=auth_headers(account["access_token"])).status_code == 429


@pytest.mark.parametrize("provider_state", ["disabled", "quota", "failure"])
def test_password_change_succeeds_when_courtesy_email_unavailable(
    client,
    monkeypatch,
    password_settings,
    provider_state,
):
    account = register_user(client)
    password_settings.reset_mock()
    if provider_state == "disabled":
        monkeypatch.setattr(settings, "mail_provider", "disabled")
    elif provider_state == "quota":
        monkeypatch.setattr(settings, "mail_daily_limit", 1)
    else:
        password_settings.side_effect = MailDeliveryError("provider recipient/token detail")
    assert (
        client.post(
            CHANGE,
            json={"current_password": TEST_PASSWORD, "password": NEW_PASSWORD},
            headers=auth_headers(account["access_token"]),
        ).status_code
        == 200
    )
    assert password_settings.call_count == (1 if provider_state == "failure" else 0)
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "user@example.com", "password": NEW_PASSWORD}
        ).status_code
        == 200
    )


def test_stale_service_account_is_rechecked_under_lock(db_session):
    user = AuthService(db_session).signup(
        email="stale@example.com", name="Stale", password=TEST_PASSWORD
    )
    # Keep the loaded instance stale, as a concurrent password reset would do.
    db_session.execute(
        update(User).where(User.id == user.id).values(session_version=1),
        execution_options={"synchronize_session": False},
    )
    with pytest.raises(AuthenticationError, match="Account changed"):
        AccountPasswordService(db_session).change_password(
            user, TEST_PASSWORD, NEW_PASSWORD, "test-ip"
        )


@pytest.fixture
def password_factory(db_engine, tmp_path):
    engine = db_engine
    if engine.dialect.name == "sqlite":
        engine = create_db_engine(f"sqlite:///{tmp_path / 'password-concurrency.db'}")
        Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    if engine is not db_engine:
        engine.dispose()


@pytest.mark.parametrize("adding", [False, True])
def test_concurrent_password_mutation_commits_only_once(password_factory, adding):
    with password_factory() as db:
        user = User(email="race@example.com", name="Race", password_hash=None)
        if not adding:
            from app.core.security import hash_password

            user.password_hash = hash_password(TEST_PASSWORD)
        db.add(user)
        db.flush()
        db.add(ProviderIdentity(user_id=user.id, provider="google", subject="owner-sub"))
        db.commit()
        user_id = user.id
        nonce, signed = (
            AccountPasswordService(db).add_challenge(user, "seed") if adding else (None, None)
        )
    barrier = Barrier(2)

    def mutate(index):
        with password_factory() as db:
            current = db.get(User, user_id)
            barrier.wait(timeout=10)
            try:
                service = AccountPasswordService(db)
                if adding:
                    service.add_password(
                        current, "test-id-token", signed, NEW_PASSWORD, f"ip-{index}"
                    )
                else:
                    service.change_password(current, TEST_PASSWORD, NEW_PASSWORD, f"ip-{index}")
                return "success"
            except AuthenticationError:
                return "invalid"

    with (
        patch("app.services.account_passwords.verify_google", return_value={"sub": "owner-sub"}),
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        assert sorted(pool.map(mutate, (1, 2))) == ["invalid", "success"]
    with password_factory() as db:
        assert db.get(User, user_id).session_version == 1
        if adding:
            assert db.scalar(select(SecurityToken)).token_hash == hash_security_token(nonce)
            assert db.scalar(select(SecurityToken)).consumed_at is not None
