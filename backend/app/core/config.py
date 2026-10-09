"""Typed application settings loaded from environment variables / .env."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import EmailStr, Field, TypeAdapter, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

from .database_url import normalize_database_url

# Sentinel default; production startup refuses to run with it (see validator).
_DEFAULT_SECRET = "change-me-in-.env"  # noqa: S105


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        hide_input_in_errors=True,
    )

    # --- Application ---
    app_env: Literal["local", "test", "production"] = "local"
    log_level: str = "INFO"

    # --- Database ---
    database_url: str = "sqlite:///./searchscribe.db"

    # --- Auth ---
    secret_key: str = _DEFAULT_SECRET
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 14
    jwt_algorithm: str = "HS256"
    google_client_id: str = ""

    # --- Transactional security email ---
    mail_provider: Literal["disabled", "brevo"] = "disabled"
    public_site_url: str = "http://localhost:3000"
    mail_from_name: str = "SearchScribe AI"
    mail_from_email: str = ""
    brevo_api_key: str = ""
    mail_timeout_seconds: int = Field(default=10, ge=1, le=30)
    password_reset_expire_minutes: int = Field(default=30, ge=5, le=60)
    email_verification_expire_hours: int = Field(default=24, ge=1, le=48)
    security_email_requests_per_hour: int = Field(default=3, ge=1, le=10)
    security_ip_requests_per_hour: int = Field(default=20, ge=1, le=100)
    mail_daily_limit: int = Field(default=250, ge=1, le=299)
    mail_recovery_reserve: int = Field(default=50, ge=0, le=298)

    # --- CORS ---
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # --- AI provider ---
    ai_provider: Literal["gemini", "mock"] = "gemini"
    ai_model: str = "gemini-2.5-flash"
    gemini_api_key: str = ""
    ai_timeout_seconds: int = 60
    ai_max_retries: int = 2
    ai_max_output_tokens: int = 8192

    # --- Request limits ---
    max_query_length: int = 500
    max_rewrite_input_length: int = 20000
    max_article_title_length: int = 200

    # --- Rate limits (requests per minute) ---
    rate_limit_auth_per_minute: int = 10
    rate_limit_generation_per_minute: int = 5

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @field_validator("public_site_url")
    @classmethod
    def _validate_public_site_url(cls, value: str) -> str:
        parsed = urlsplit(value.strip())
        try:
            _ = parsed.port
        except ValueError:
            raise ValueError("PUBLIC_SITE_URL must be a valid site origin") from None
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or any(character.isspace() for character in value)
            or (
                parsed.scheme == "http"
                and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            )
        ):
            raise ValueError(
                "PUBLIC_SITE_URL must be an HTTPS site origin (HTTP localhost is local only)"
            )
        return value.strip().rstrip("/")

    @model_validator(mode="after")
    def _validate_mail(self) -> Settings:
        if self.mail_recovery_reserve >= self.mail_daily_limit:
            raise ValueError("MAIL_RECOVERY_RESERVE must be below MAIL_DAILY_LIMIT")
        if self.mail_provider == "brevo":
            if not self.brevo_api_key.strip():
                raise ValueError("BREVO_API_KEY is required when MAIL_PROVIDER=brevo")
            self.brevo_api_key = self.brevo_api_key.strip()
            try:
                self.mail_from_email = str(
                    TypeAdapter(EmailStr).validate_python(self.mail_from_email)
                )
            except ValueError:
                raise ValueError("MAIL_FROM_EMAIL must be valid when MAIL_PROVIDER=brevo") from None
            if not self.mail_from_name.strip():
                raise ValueError("MAIL_FROM_NAME must not be blank")
            if self.is_production and urlsplit(self.public_site_url).scheme != "https":
                raise ValueError("Production security email requires an HTTPS PUBLIC_SITE_URL")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _validate_security(self) -> Settings:
        if not self.is_production:
            return self
        if self.secret_key == _DEFAULT_SECRET or len(self.secret_key) < 32:
            raise ValueError(
                "SECRET_KEY must contain at least 32 characters in production; "
                "generate a strong random value"
            )
        if make_url(self.database_url).get_backend_name() != "postgresql":
            raise ValueError("Production requires persistent PostgreSQL; SQLite is local/test only")
        if self.ai_provider == "mock":
            raise ValueError("AI_PROVIDER=mock is local/test only")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
