"""Optional Groq JSON provider with bounded transport and local schema validation."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, TypeVar

import httpx
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
from .schemas import GeneratedArticle, GeneratedArticleWithSeo

GROQ_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"

T = TypeVar("T", bound=BaseModel)


def _strict_json_schema(value: dict[str, Any]) -> dict[str, Any]:
    """Adapt optional/default Pydantic properties to Groq's strict wire schema.

    Nullable unions and semantic constraints stay intact. Validation still uses
    the original application model; this only constrains what the API may emit.
    """
    def convert(node: Any) -> Any:
        if isinstance(node, list):
            return [convert(item) for item in node]
        if not isinstance(node, dict):
            return node
        result = {key: convert(item) for key, item in node.items() if key != "default"}
        if result.get("type") == "object":
            result["additionalProperties"] = False
            result["required"] = list(result.get("properties", {}))
        return result

    return convert(value)


def _request_schema(schema: type[BaseModel]) -> dict[str, Any]:
    """Ask for editorial content; section IDs and research belong to the server."""
    wire = schema.model_json_schema()
    if schema in {GeneratedArticle, GeneratedArticleWithSeo}:
        wire["properties"].pop("research", None)
        definitions = wire.get("$defs", {})
        definitions["ArticleSection"]["properties"].pop("id", None)
        definitions.pop("ResearchSummary", None)
        definitions.pop("ResearchSource", None)
    return _strict_json_schema(wire)


async def _complete(payload: dict[str, object], api_key: str) -> dict[str, object]:
    """Make one request. Retry and fallback are owned by the routing layer."""
    timeout_seconds = effective_timeout_seconds()
    try:
        async with asyncio.timeout(timeout_seconds):
            async with httpx.AsyncClient(
                timeout=timeout_seconds,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                async with client.stream(
                    "POST",
                    GROQ_COMPLETIONS_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "Accept-Encoding": "identity",
                    },
                    json=payload,
                ) as response:
                    status = response.status_code
                    if status in {408, 429} or status >= 500:
                        raise TransientLLMError(f"groq request failed ({status})")
                    if status != 200:
                        raise PermanentLLMError(f"groq request rejected ({status})")
                    if response.headers.get("content-encoding", "").lower() not in {
                        "", "identity",
                    }:
                        raise SchemaValidationError("groq response encoding is unsupported")
                    raw_length = response.headers.get("content-length")
                    if raw_length is not None:
                        try:
                            oversized = int(raw_length) > settings.groq_max_response_bytes
                        except ValueError:
                            raise SchemaValidationError(
                                "groq response envelope is invalid"
                            ) from None
                        if oversized:
                            raise SchemaValidationError("groq response exceeded the size limit")
                    chunks = bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=4096):
                        if len(chunks) + len(chunk) > settings.groq_max_response_bytes:
                            raise SchemaValidationError("groq response exceeded the size limit")
                        chunks.extend(chunk)
    except (httpx.TimeoutException, TimeoutError):
        raise TransientLLMError("groq request timed out") from None
    except httpx.HTTPError:
        raise TransientLLMError("groq transport failed") from None

    try:
        result = json.loads(chunks)
    except (ValueError, UnicodeDecodeError):
        raise SchemaValidationError("groq response envelope is invalid") from None
    if not isinstance(result, dict):
        raise SchemaValidationError("groq response envelope is invalid")
    return result


def _response_text(response: dict[str, object]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise SchemaValidationError("groq response envelope is invalid")
    choice = choices[0]
    message = choice.get("message")
    if not isinstance(message, dict):
        raise SchemaValidationError("groq response envelope is invalid")
    if message.get("refusal") or choice.get("finish_reason") == "content_filter":
        raise PermanentLLMError("groq declined the request")
    if choice.get("finish_reason") != "stop":
        raise SchemaValidationError("groq response was incomplete")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise SchemaValidationError("groq returned no JSON output")
    return content


def _usage_count(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


class GroqProvider:
    name = "groq"

    def __init__(self, model: str | None = None) -> None:
        self.model = settings.ai_model if model is None else model

    def generate(
        self,
        prompt_name: str,
        prompt_version: str,
        variables: dict[str, str],
        schema: type[T],
    ) -> ProviderResponse[T]:
        if not self.model.strip() or not settings.groq_api_key.strip():
            raise PermanentLLMError("groq model and API key must be configured")
        prompt = render_prompt(prompt_name, prompt_version, variables)
        strict_schema = _request_schema(schema)
        schema_json = json.dumps(strict_schema, separators=(",", ":"))
        instruction = (
            "Return one JSON object matching the schema. No Markdown or commentary. "
            "Include every required property at every nesting level, even when unused. "
            "Use an empty array for unused array fields, never omit them. "
            "Use null only where the schema permits it."
        )
        if variables.get("research_status") == "sources_retrieved":
            instruction += (
                " Cite supported claims inline in the introduction and section paragraphs "
                "using the supplied source IDs in square brackets. A bibliography or "
                "research metadata alone does not attribute those claims. Use only "
                "explicit reference facts: do not add numerical conversions, comparisons, "
                "superlatives, release timing or latest/newest claims that the references "
                "do not establish. A citation does not support an invented extrapolation."
            )
        # Also show the schema to the model in strict mode. Live responses can be
        # rejected upstream for omitted nested fields despite strict=True; the
        # response_format alone is not a substitute for complete instructions.
        instruction += "\n" + schema_json
        if len(prompt) + len(instruction) + (
            len(schema_json) if settings.groq_json_mode == "json_schema" else 0
        ) > settings.groq_max_input_chars:
            # Preserve complete evidence: never silently truncate the research context.
            raise PermanentLLMError("groq request exceeded the configured input limit")
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": instruction},
                {"role": "user", "content": prompt},
            ],
            "response_format": (
                {"type": "json_schema", "json_schema": {
                    "name": schema.__name__, "strict": True,
                    "schema": strict_schema,
                }} if settings.groq_json_mode == "json_schema" else {"type": "json_object"}
            ),
            "max_completion_tokens": settings.groq_max_output_tokens,
            "stream": False,
        }
        if settings.groq_reasoning_effort:
            payload["reasoning_effort"] = settings.groq_reasoning_effort
        started = time.perf_counter()
        response = asyncio.run(_complete(payload, settings.groq_api_key))
        text = _response_text(response)
        try:
            if schema in {GeneratedArticle, GeneratedArticleWithSeo}:
                payload_content = json.loads(text)
                if isinstance(payload_content, dict):
                    # Compatibility mode can still emit unwanted keys. Never
                    # accept model-owned provenance or depend on invented IDs.
                    payload_content.pop("research", None)
                    sections = payload_content.get("sections")
                    if isinstance(sections, list):
                        for section in sections:
                            if isinstance(section, dict):
                                section.pop("id", None)
                data = schema.model_validate(payload_content)
            else:
                data = schema.model_validate_json(text)
        except (ValidationError, ValueError):
            raise SchemaValidationError("groq JSON output failed schema validation") from None
        usage = response.get("usage")
        counts = usage if isinstance(usage, dict) else {}
        return ProviderResponse(
            data=data,
            provider=self.name,
            model=self.model,
            input_tokens=_usage_count(counts.get("prompt_tokens")),
            output_tokens=_usage_count(counts.get("completion_tokens")),
            latency_ms=int((time.perf_counter() - started) * 1000),
            prompt_name=prompt_name,
            prompt_version=prompt_version,
        )
