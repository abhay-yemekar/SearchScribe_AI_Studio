"""Gemini structured output with cancellable, request-scoped transport deadlines."""

from __future__ import annotations

import asyncio
import time
from typing import TypeVar

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, ValidationError

from ..core.config import settings
from .base import (
    PermanentLLMError,
    ProviderResponse,
    SchemaValidationError,
    TransientLLMError,
)
from .budget import effective_timeout_seconds
from .prompts import render_prompt
from .rate_limits import gemini_rate_limit

# Codes worth retrying: rate limit + server-side failures.
_TRANSIENT_CODES = {408, 429, 500, 502, 503, 504}

T = TypeVar("T", bound=BaseModel)


def _validate_completion(response: types.GenerateContentResponse) -> None:
    feedback = getattr(response, "prompt_feedback", None)
    block_reason = getattr(feedback, "block_reason", None)
    if block_reason and block_reason != types.BlockedReason.BLOCKED_REASON_UNSPECIFIED:
        raise PermanentLLMError("gemini declined the request")
    for candidate in getattr(response, "candidates", None) or []:
        reason = candidate.finish_reason
        if reason in {
            types.FinishReason.SAFETY, types.FinishReason.RECITATION,
            types.FinishReason.BLOCKLIST, types.FinishReason.PROHIBITED_CONTENT,
            types.FinishReason.SPII, types.FinishReason.IMAGE_SAFETY,
            types.FinishReason.IMAGE_PROHIBITED_CONTENT, types.FinishReason.IMAGE_RECITATION,
        } or any(rating.blocked for rating in candidate.safety_ratings or []):
            raise PermanentLLMError("gemini declined the request")
        if reason != types.FinishReason.STOP:
            raise SchemaValidationError("gemini response was incomplete")

async def _generate_content(
    *, model: str, prompt: str, config: types.GenerateContentConfig,
    timeout_seconds: float,
) -> types.GenerateContentResponse:
    # A new async client belongs to this worker's event loop and is closed on
    # cancellation. Reusing one across asyncio.run loops breaks later requests.
    async with asyncio.timeout(timeout_seconds):
        with genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(
                timeout=max(1, int(timeout_seconds * 1000)),
                retry_options=types.HttpRetryOptions(attempts=1),
                async_client_args={"trust_env": False},
            ),
        ) as sdk_client:
            async with sdk_client.aio as client:
                return await client.models.generate_content(
                    model=model, contents=[prompt], config=config,
                )


class GeminiProvider:
    name = "gemini"

    def __init__(
        self, *, model: str | None = None, compact_schema: bool = False,
        temperature: float = 0.7,
        thinking_budget: int | None = None,
    ) -> None:
        self.model = model if model is not None else settings.ai_model
        self.compact_schema = compact_schema
        self.temperature = temperature
        self.thinking_budget = thinking_budget

    def generate(
        self,
        prompt_name: str,
        prompt_version: str,
        variables: dict[str, str],
        schema: type[T],
    ) -> ProviderResponse[T]:
        prompt = render_prompt(prompt_name, prompt_version, variables)
        timeout_seconds = effective_timeout_seconds()
        config = types.GenerateContentConfig(
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            response_mime_type="application/json",
            response_schema=schema,
            temperature=self.temperature,
            max_output_tokens=settings.ai_max_output_tokens,
        )
        if self.thinking_budget is not None:
            config.thinking_config = types.ThinkingConfig(thinking_budget=self.thinking_budget)
        if self.compact_schema:
            # Large bounded review arrays can exceed Gemini's decoder-state
            # budget. Keep the structural wire schema small; the ORIGINAL
            # Pydantic schema still enforces every length/ID/coverage constraint.
            def compact(value):
                if isinstance(value, list):
                    return [compact(item) for item in value]
                if isinstance(value, dict):
                    return {key: compact(item) for key, item in value.items()
                            if key not in {"minLength", "maxLength", "pattern", "maxItems"}
                            and (key != "minItems" or item == 1)}
                return value

            config.response_schema = None
            config.response_json_schema = compact(schema.model_json_schema())
        started = time.perf_counter()

        try:
            response = asyncio.run(_generate_content(
                model=self.model, prompt=prompt, config=config, timeout_seconds=timeout_seconds,
            ))
        except genai_errors.APIError as exc:
            code = getattr(exc, "code", None)
            if code == 429:
                retry_after = (exc.response.headers.get("retry-after")
                               if isinstance(exc.response, httpx.Response) else None)
                raise gemini_rate_limit(exc.details, retry_after) from None
            if code in _TRANSIENT_CODES:
                raise TransientLLMError(f"gemini api error {code}") from None
            raise PermanentLLMError(f"gemini api error {code}") from None
        except (httpx.TimeoutException, httpx.TransportError, TimeoutError):
            raise TransientLLMError("gemini transport unavailable") from None

        latency_ms = int((time.perf_counter() - started) * 1000)
        _validate_completion(response)
        text = (response.text or "").strip()
        if not text:
            raise SchemaValidationError("empty response from gemini")

        try:
            data = schema.model_validate_json(text)
        except (ValidationError, ValueError):
            raise SchemaValidationError("gemini payload failed validation") from None

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
