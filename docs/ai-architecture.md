# AI Architecture

## Provider abstraction

All LLM access goes through one protocol (`app/ai/base.py`):

```python
class LLMProvider(Protocol):
    name: str
    model: str
    def generate(self, prompt_name, prompt_version, variables, schema) -> ProviderResponse[T]
```

Implementations:

| Provider | File | Notes |
| --- | --- | --- |
| `GeminiProvider` | `app/ai/gemini.py` | google-genai SDK, structured JSON output (`response_schema` = Pydantic model), timeouts, token usage captured |
| `MockProvider` | `app/ai/mock.py` | deterministic, offline; test hooks for transient/permanent failure simulation |

Selection is config-driven (`AI_PROVIDER`), resolved through `get_provider()`. Adding OpenAI/Groq/Ollama later = one new file + one factory entry + env vars; no business-logic changes.

## Failure taxonomy and retries

- `TransientLLMError` — timeouts, 429, 5xx. Retried with exponential backoff + jitter, bounded by `AI_MAX_RETRIES`.
- `PermanentLLMError` — auth failures, bad requests, blocked content. Never retried.
- `SchemaValidationError` — provider answered but the payload failed Pydantic validation. Never retried blindly.

**No silent fallbacks.** The original codebase returned fabricated placeholder articles when Gemini failed while reporting success. That is gone: a failed generation returns `502 GENERATION_FAILED` and records the failure. The only degradation is SEO → deterministic fallback metadata, which is clearly derived from real article content, not fabricated.

## Prompts

Prompts are versioned files in `app/ai/prompts/` rendered with Jinja2 (strict undefined):

- `article_generation_v1.md`
- `seo_generation_v1.md`
- `rewrite_v1.md` (style guidance injected from `app/ai/styles.py`)

Every generation row records `prompt_name` + `prompt_version`, so AI behavior is reproducible and debuggable.

## Structured output

The LLM returns structured JSON validated into Pydantic models:

- `GeneratedArticle` — title, introduction, sections (heading/paragraphs/bullets), conclusion
- `SeoResult` — title, description, keywords, OG fields

Markdown (`to_markdown()`) and HTML are **derived deterministically** from the structure. The LLM never produces HTML.

## Rendering pipeline

```
GeneratedArticle + SeoResult
  → Jinja2 template (autoescape on)      # safe by construction
  → sanitize_document (nh3)               # defense in depth
  → stored/served HTML
```

`sanitize_document` keeps the document skeleton (`<!DOCTYPE>`, `<head>` with template-generated meta tags) while sanitizing the body fragment — nh3 is fragment-oriented and would otherwise drop the wrappers.

## SEO normalization

`app/ai/validation.py` clamps LLM output into deterministic bounds: title ≤ 60 chars (word-boundary truncation), description ≤ 160, keywords lower-cased, deduplicated, capped at 12. Identical rules are surfaced in the frontend's length meters.

## Cost & observability

Every call writes a `generations` row: provider, model, prompt name/version, input/output tokens, latency, status, error code. Structured logs emit `generation.started/completed/failed`, `generation.seo_fallback`, `llm.transient_retry`. Bounded limits: `AI_MAX_OUTPUT_TOKENS`, `AI_TIMEOUT_SECONDS`, `MAX_QUERY_LENGTH`, `MAX_REWRITE_INPUT_LENGTH`.
