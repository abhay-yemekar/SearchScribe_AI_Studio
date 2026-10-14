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
| `GroqProvider` | `app/ai/groq.py` | strict JSON schema by default, explicit JSON-object compatibility mode, bounded HTTP response and local Pydantic validation |
| `MockProvider` | `app/ai/mock.py` | deterministic, offline; test hooks for transient/permanent failure simulation |

Selection is config-driven (`AI_PROVIDER` + exact `AI_MODEL`), resolved through
`get_provider()`. Models never depend on the topic. Blank `AI_FALLBACK_PROVIDER`
and `AI_FALLBACK_MODEL` disable fallback; setting both enables one explicitly
selected secondary route. The secondary provider requires its own key, unless
it uses the same provider with a different model. Mock stays completely offline.

## Failure taxonomy and retries

- `TransientLLMError` — transport failures, timeouts, 429, 5xx. Primary retries
  have exponential backoff + jitter, bounded by `AI_MAX_RETRIES` and the shared
  remaining deadline. One configured fallback is attempted after a transient
  primary failure, with the identical prompt and source bundle.
- `PermanentLLMError` — auth failures, bad requests, blocked content. Never retried.
- `SchemaValidationError` — provider answered but the payload failed Pydantic validation. Never retried blindly.

The external-call budget (`AI_OPERATION_TIMEOUT_SECONDS`, default 100 seconds)
includes research, primary attempts/backoff, one fallback and one SEO repair.
Async transports cancel and close on expiry; there is no background generation
thread continuing after a timeout. A configured fallback reserves up to 20 seconds
of the remaining budget. SDK retries are disabled so attempts cannot multiply.
Database commits and deterministic rendering remain outside this network budget.
An exhausted budget follows the generation/rewrite error path; failed operations never
create a placeholder article or version.

Fallback does not bypass missing current evidence, content refusals, bad keys,
invalid configuration or malformed generated content. SEO repair remains one
direct call with the remaining budget; a failed repair preserves the valid
article and marks its metadata for review. Error logs contain sanitized categories,
not upstream response bodies, keys, source excerpts or validation input.

An article provider failure returns `502 GENERATION_FAILED`; it never creates a
placeholder article. A valid article is retained if its SEO cannot be completed.
That degradation uses text from the article and carries a visible `needs_review`
status. It does not claim the fallback is optimized or verified.

## Prompts

Prompts are versioned files in `app/ai/prompts/` rendered with Jinja2 (strict undefined):

- Versioned article prompts include the actual query, current UTC date and
  bounded untrusted research context. Normal generation returns article and SEO
  together in one structured response.
- Article prompt v4 sizes the article to the available evidence instead of
  demanding a fixed number of sections or paragraphs. It preserves units and
  attribution and asks the writer to name evidence gaps instead of filling them
  with unsupported explanations. This is a generation instruction, not a
  deterministic factual validator.
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

Successful generation rows record the provider/model that actually answered,
including a fallback answer. Failed rows record the last attempted route and
sanitized error category. Structured logs record retries and fallback selection.
Groq has separate `GROQ_MAX_INPUT_CHARS`, `GROQ_MAX_OUTPUT_TOKENS` and response-byte
caps; an oversized source bundle is rejected, never silently truncated.

## Comparing free models

Use `backend/scripts/evaluate_generation.py` for the 20-case evaluation set.
The default is a dry run; `--live` is explicit. It uses an isolated in-memory
database, disables retries/fallback for fair comparisons, and reports generated
drafts separately from evidence-related declines. Frozen public source bundles
let models receive identical evidence, but do not establish live retrieval quality.
Reports require manual factual review; a schema pass is not a fact-check.

To compare models against actual search results, first run the same CLI with
`--live --collect-sources --progress`. This performs public web search only,
without a model call or application database, and saves reusable source bundles.
Pass the resulting `source-bundles.json` to each model with `--source-bundles`.
An explicit `--case-delay-seconds` between 0 and 60 can pace evaluation on Free
accounts; `--progress` prints public case IDs and safe statuses without prompts
or SDK exception bodies. A missing-evidence decline is reported separately from
schema success. Frozen comparisons do not measure how future searches will rank.

The current primary remains unchanged until a candidate is benchmarked. Current
official references: [Gemini models](https://ai.google.dev/gemini-api/docs/models),
[Gemini free pricing](https://ai.google.dev/gemini-api/docs/pricing),
[Groq models](https://console.groq.com/docs/models), and
[Groq account limits](https://console.groq.com/docs/rate-limits). Keep accounts on
Free with paid upgrades disabled; published allowances can differ from account
limits. The personal Render key is configured, but fallback remains disabled
pending a broader factual quality gate. Live pilot responses exposed missing
citations and unsupported extrapolation. Strict output and inline-citation guards
improve structural reliability; they do not establish that each claim is true.
