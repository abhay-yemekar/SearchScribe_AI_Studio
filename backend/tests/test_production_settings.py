"""Hosting settings fail closed without touching a production database."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.core.database_url import normalize_database_url


def production_settings(**overrides: object) -> Settings:
    values = {
        "app_env": "production",
        "secret_key": "test-only-key-with-at-least-32-characters",
        "database_url": "postgresql://test:test@localhost/searchscribe_test?sslmode=require",
        "ai_provider": "gemini",
        **overrides,
    }
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize("secret", ["", "short", "change-me-in-.env"])
def test_production_rejects_weak_secret(secret: str) -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        production_settings(secret_key=secret)


def test_production_rejects_ephemeral_sqlite() -> None:
    with pytest.raises(ValidationError, match="persistent PostgreSQL"):
        production_settings(database_url="sqlite:///./production.db")


def test_production_rejects_mock_generation() -> None:
    with pytest.raises(ValidationError, match="local/test only"):
        production_settings(ai_provider="mock")


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+psycopg"])
def test_hosting_url_uses_installed_driver_and_preserves_tls(scheme: str) -> None:
    settings = production_settings(
        database_url=f"{scheme}://writer:p%40ss%25word@localhost/searchscribe_test?sslmode=require"
    )
    url = make_url(settings.database_url)
    assert url.drivername == "postgresql+psycopg"
    assert url.password == "p@ss%word"
    assert url.query["sslmode"] == "require"


def test_invalid_database_url_error_does_not_echo_credentials() -> None:
    with pytest.raises(ValueError) as exc:
        normalize_database_url("invalid-secret-connection-string")
    assert "invalid-secret-connection-string" not in str(exc.value)


def test_startup_validation_does_not_print_secret_environment_values() -> None:
    with pytest.raises(ValidationError) as exc:
        production_settings(
            database_url="sqlite://", gemini_api_key="private-key-must-not-be-logged"
        )
    assert "private-key-must-not-be-logged" not in str(exc.value)


def test_local_sqlite_and_mock_remain_available() -> None:
    settings = Settings(
        _env_file=None, app_env="local", database_url="sqlite://", ai_provider="mock"
    )
    assert settings.database_url == "sqlite://"


@pytest.mark.parametrize(
    "origin",
    [
        "https://example.com/reset",
        "https://example.com?next=other",
        "https://example.com#secret",
        "https://user:pass@example.com",
        "http://example.com",
        "https://example.com:wrong",
    ],
)
def test_security_mail_rejects_untrusted_link_origin_shapes(origin: str) -> None:
    with pytest.raises(ValidationError, match="PUBLIC_SITE_URL"):
        production_settings(public_site_url=origin)


def test_mail_provider_requires_complete_sender_config_and_https() -> None:
    with pytest.raises(ValidationError, match="BREVO_API_KEY"):
        production_settings(mail_provider="brevo", brevo_api_key="")
    with pytest.raises(ValidationError, match="MAIL_FROM_EMAIL"):
        production_settings(
            mail_provider="brevo", brevo_api_key="test-api-key", mail_from_email="invalid"
        )
    with pytest.raises(ValidationError, match="HTTPS PUBLIC_SITE_URL"):
        production_settings(
            mail_provider="brevo",
            brevo_api_key="test-api-key",
            mail_from_email="mail@example.com",
            public_site_url="http://localhost:3000",
        )
    configured = production_settings(
        mail_provider="brevo",
        brevo_api_key="  test-api-key\n",
        mail_from_email="mail@example.com",
        public_site_url="https://searchscribe-ai.vercel.app/",
    )
    assert configured.public_site_url == "https://searchscribe-ai.vercel.app"
    assert configured.brevo_api_key == "test-api-key"


def test_daily_mail_limit_stays_below_free_quota_and_has_recovery_capacity() -> None:
    with pytest.raises(ValidationError):
        production_settings(mail_daily_limit=300)
    with pytest.raises(ValidationError, match="MAIL_RECOVERY_RESERVE"):
        production_settings(mail_daily_limit=50, mail_recovery_reserve=50)
