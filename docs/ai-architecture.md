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

An article provider failure returns `502 GENERATION_FAILED`; it never creates a
placeholder article. A valid article is retained if its SEO cannot be completed.
That degradation uses text from the article and carries a visible `needs_review`
status. It does not claim the fallback is optimized or verified.

## Prompts

Prompts are versioned files in `app/ai/prompts/` rendered with Jinja2 (strict undefined):

- Versioned article prompts include the actual query, current UTC date and
  bounded untrusted research context. Normal generation returns article and SEO
  together in one structured response.
- A separate SEO prompt is used only for one targeted repair when the combined
  response has missing, malformed or unsuitable metadata. This repair has no
  retry loop; the valid article survives an unsuccessful repair.
- `rewrite_v1.md` (style guidance injected from `app/ai/styles.py`)

Every generation row records `prompt_name` + `prompt_version`, so AI behavior is reproducible and debuggable.

## Structured output

The LLM returns structured JSON validated into Pydantic models:

- `GeneratedArticle` — title, introduction, sections (heading/paragraphs/bullets), conclusion
- `SeoCandidate` — provider-written title, description, keywords and OG fields;
  malformed SEO does not invalidate an otherwise valid article.
- `SeoResult` — accepted or article-derived metadata with server-owned review status.

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

Generated SEO is checked against product targets: titles at most 60 characters,
descriptions at most 160 with a complete ending, and specific keywords. These
are display targets, not search-engine hard limits or proof of semantic quality.
Manual edits retain their separate validation bounds and visible length meters.

Review state is stored in the existing version SEO snapshot, so no database
migration is needed. `generated` means AI metadata passed structural checks,
`needs_review` means generation degraded or article content changed, `edited`
means the user changed SEO fields, and `unknown` covers legacy snapshots without
recorded provenance. Restore and duplicate preserve the snapshot state. Clients
and models cannot assign a trusted review state, and no state means fact-checked.

## Cost & observability

Every call writes a `generations` row: provider, model, prompt name/version, input/output tokens, latency, status, error code. Structured logs emit `generation.started/completed/failed`, `generation.seo_fallback`, `llm.transient_retry`. Bounded limits: `AI_MAX_OUTPUT_TOKENS`, `AI_TIMEOUT_SECONDS`, `MAX_QUERY_LENGTH`, `MAX_REWRITE_INPUT_LENGTH`.
