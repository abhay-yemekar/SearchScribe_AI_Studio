"""Provider factory: selection driven entirely by configuration."""

from __future__ import annotations

from functools import lru_cache

from ..core.config import settings
from .base import LLMProvider
from .gemini import GeminiProvider
from .mock import MockProvider


class UnknownProviderError(ValueError):
    pass


@lru_cache(maxsize=1)
def get_provider() -> LLMProvider:
    """Return the configured provider. Adding one = new file + one entry here."""
    if settings.ai_provider == "gemini":
        if not settings.gemini_api_key:
            raise UnknownProviderError(
                "AI_PROVIDER=gemini requires GEMINI_API_KEY to be set"
            )
        return GeminiProvider()
    if settings.ai_provider == "mock":
        return MockProvider()
    raise UnknownProviderError(f"unknown AI_PROVIDER: {settings.ai_provider}")


def reset_provider_cache() -> None:
    """Test hook: force re-resolution after settings change."""
    get_provider.cache_clear()
