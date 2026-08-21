"""Gemini provider on the maintained google-genai SDK with structured output."""

from __future__ import annotations

import logging
import time

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from ..core.config import settings
from .base import PermanentLLMError, ProviderResponse, SchemaValidationError, TransientLLMError
from .prompts import render_prompt

logger = logging.getLogger(__name__)

# Codes worth retrying: rate limit + server-side failures.
_TRANSIENT_CODES = {429, 500, 502, 503, 504}

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(
                timeout=settings.ai_timeout_seconds * 1000
            ),
        )
    return _client


class GeminiProvider:
    name = "gemini"
    model: str = settings.ai_model

    def generate(
        self,
        prompt_name: str,
        prompt_version: str,
        variables: dict[str, str],
        schema: type,
    ) -> ProviderResponse:
        prompt = render_prompt(prompt_name, prompt_version, variables)
        started = time.perf_counter()

        try:
            response = _get_client().models.generate_content(
                model=self.model,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0.7,
                    max_output_tokens=settings.ai_max_output_tokens,
                ),
            )
        except genai_errors.APIError as exc:
            code = getattr(exc, "code", None)
            if code in _TRANSIENT_CODES:
                raise TransientLLMError(f"gemini api error {code}") from exc
            raise PermanentLLMError(f"gemini api error {code}: {exc}") from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        text = (response.text or "").strip()
        if not text:
            raise SchemaValidationError("empty response from gemini")

        try:
            data = schema.model_validate_json(text)
        except Exception as exc:
            raise SchemaValidationError(f"gemini payload failed validation: {exc}") from exc

        usage = response.usage_metadata
        return ProviderResponse(
            data=data,
            provider=self.name,
            model=self.model,
            input_tokens=usage.prompt_token_count if usage else None,
            output_tokens=usage.candidates_token_count if usage else None,
            latency_ms=latency_ms,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
        )
