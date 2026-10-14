"""Provider factory: selection driven entirely by configuration."""

from __future__ import annotations

from functools import lru_cache

from ..core.config import settings
from .base import LLMProvider
from .gemini import GeminiProvider
from .mock import MockProvider


class UnknownProviderError(ValueError):
    pass


def _build_provider(name: str, model: str) -> LLMProvider:
    if name == "gemini":
        if not settings.gemini_api_key:
            raise UnknownProviderError(
                "AI_PROVIDER=gemini requires GEMINI_API_KEY to be set"
            )
        return GeminiProvider(model=model)
    if name == "groq":
        if not settings.groq_api_key.strip():
            raise UnknownProviderError("AI_PROVIDER=groq requires GROQ_API_KEY to be set")
        from .groq import GroqProvider

        return GroqProvider(model=model)
    if name == "mock":
        return MockProvider()
    raise UnknownProviderError(f"unknown AI_PROVIDER: {name}")


@lru_cache(maxsize=1)
def get_provider() -> LLMProvider:
    """Return only the configured primary; models never depend on query topics."""
    return _build_provider(settings.ai_provider, settings.ai_model)


@lru_cache(maxsize=1)
def get_fallback_provider() -> LLMProvider | None:
    if not settings.ai_fallback_provider:
        return None
    return _build_provider(settings.ai_fallback_provider, settings.ai_fallback_model)


def reset_provider_cache() -> None:
    """Test hook: force re-resolution after settings change."""
    get_provider.cache_clear()
    get_fallback_provider.cache_clear()
