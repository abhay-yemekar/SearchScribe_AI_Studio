"""Typed application settings loaded from environment variables / .env."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Sentinel default; production startup refuses to run with it (see validator).
_DEFAULT_SECRET = "change-me-in-.env"  # noqa: S105


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
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

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _validate_security(self) -> Settings:
        if self.is_production and self.secret_key == _DEFAULT_SECRET:
            raise ValueError(
                "SECRET_KEY must be set to a strong random value in production"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
