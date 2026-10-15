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

The default and sample writer model are now `gemini-3.8-flash`, an explicit
version with a documented free tier. Existing `.env` and hosting `AI_MODEL`
values override that default and require a deliberate configuration update;
changing this source default alone does not migrate a deployed service. Free
availability and capacity remain account-specific. The release's isolated live
qualification records and deployed configuration must be checked separately.

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
- Article prompt v5 sizes the article to the available evidence instead of
  demanding a fixed number of sections or paragraphs. It preserves units and
  attribution and asks the writer to name evidence gaps instead of filling them
  with unsupported explanations. This is a generation instruction, not a
  deterministic factual validator.
- With live research configured, `research_planning/v1` classifies reference,
  reporting, historical or general intent in one call capped at 15 seconds.
  Unresolved identity/location ambiguity returns `TOPIC_CLARIFICATION_REQUIRED`
  before searching or persisting a draft. The workspace retains the topic and
  asks the user to add the missing detail. A planning failure stops clearly.
- The original query always runs. At most one model-proposed complementary query
  searches for original evidence, without a topic/provider domain allowlist.
  The original search uses basic depth; complementary discovery uses explicit
  advanced depth (up to three Tavily credits total), concurrently within the
  research deadline. Each response is byte-bounded; results are interleaved,
  deduplicated and limited to five complete source records in the prompt.
- Reporting retains strict UTC publication/update date checks. Reference discovery
  permits older or undated maintained documents, while excluding future dates.
  This improves discovery; it does not certify primary authorship or freshness.
  V5 explicitly distinguishes event dates from roundup publication dates, asks
  for attribution of conflicting figures and names missing official evidence.
- `RESEARCH_PLANNER_PROVIDER` and `RESEARCH_PLANNER_MODEL` optionally assign a
  separately validated planner role; blank fields reuse the article provider.
  These fields do not enable article fallback. Generation metadata records
  planning usage/provider separately. Mock never calls either external role.
- `RESEARCH_PLANNER_FALLBACK_PROVIDER` / `RESEARCH_PLANNER_FALLBACK_MODEL` can
  explicitly enable one 10-second fallback attempt after a transient planner
  failure (timeout, 429, 5xx). Refusals, malformed output and clarification
  decisions never trigger it. Both attempts share the operation deadline, and
  metadata identifies the actual responding model. Default is disabled.
- Before writing from live evidence, `evidence_review/v1` selects relevant
  original passages, publisher roles, conflicts and coverage gaps in a call capped
  at 20 seconds. The server assigns passage IDs and copies the original text;
  the model selects IDs instead of retyping or paraphrasing quotes. Unknown,
  or cross-source passage IDs stop before persistence. Duplicate valid selections
  are consolidated; conflicting role assessments are treated as uncertain.
  Official-only tasks exclude material classified as secondary or uncertain from
  both the writer context and saved source list. This is model-assisted source
  selection, not proof of factual accuracy or publisher authenticity.
- `RESEARCH_REVIEWER_PROVIDER` and `RESEARCH_REVIEWER_MODEL` optionally select a
  separate evidence-review model; blank fields reuse the planner. Groq reviewers
  use JSON-object mode with local schema and passage-ownership validation. Article
  generation retains its configured strict schema. The original source records
  and selected records are saved separately in local evaluation reports.
- When `DRAFT_REVIEW_ENABLED=true`, before saving a newly researched draft,
  `draft_review/v1` checks every title,
  paragraph, bullet, conclusion and final SEO field against the original selected
  excerpts. Exact block coverage and passage ownership are enforced locally. The
  editor can replace named text blocks once (30-second call cap); changed blocks
  receive one compact `draft_recheck/v1` check using the evidence-selection role
  (20-second cap). The recheck only returns remaining issues, not further edits.
  Missing coverage, invalid corrections,
  unavailable review or unresolved findings save no new article. The writer
  reserves time for these calls within the same operation deadline; nested retry
  budgets cannot extend it. Unresearched/mock drafts do not enter this stage.
- `DRAFT_REVIEWER_PROVIDER` / `DRAFT_REVIEWER_MODEL` optionally select the final
  editor, with `DRAFT_REVIEWER_REASONING_EFFORT` for Groq. Blank fields reuse the
  evidence-selection role. Calls and revision findings are recorded separately;
  role-specific reasoning/output caps do not mutate writer configuration. Review
  remains a fallible AI excerpt-consistency check, not independent fact checking.
  Manual edits and rewrites of stored articles are not rechecked against source
  excerpts by this stage; current stored provenance contains URLs, not full text.
  The feature defaults off for existing installations until the selected free
  provider configuration has been validated. Gemini review uses a compact wire
  schema with original local bounds intact and a separately configurable
  `DRAFT_REVIEWER_THINKING_BUDGET`; it does not change the writer's settings.
- Review prompt v2 places the exact field constraints beside every block.
  In particular, corrected SEO descriptions must remain complete sentences and
  fit the product targets after removing unsupported claims. Local validation
  still rejects malformed corrections; it never clips text or adds punctuation
  to disguise a fragment. Revised body citations must agree with the selected
  supporting passage's source, just as supported original text must. Correction
  and recheck prompt versions are recorded independently, including failures.
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
The Groq request schema asks for editorial content, while the server assigns
section IDs and research provenance. The model sees required fields explicitly
even in strict mode; canonical article validation still runs before persistence.

## Comparing free models

Use `backend/scripts/evaluate_generation.py` for the 20-case evaluation set.
The default is a dry run; `--live` is explicit. It uses an isolated in-memory
database, disables retries/fallback for fair comparisons, and reports generated
drafts separately from evidence-related declines. Frozen public source bundles
let models receive identical evidence, but do not establish live retrieval quality.
Reports require manual factual review; a schema pass is not a fact-check.
Live evaluation exercises planning as well as retrieval; frozen bundles skip
planning and report that limitation, so identical-evidence comparisons stay fair.
Frozen bundles must include the original excerpt for each source, so the final
review cannot pretend to check evidence from URLs alone. Reports retain both
review passes and excerpts for manual comparison; a clean model review is not an
accuracy score.

To compare models against actual search results, first run the same CLI with
`--live --collect-sources --progress`. This performs public web search only,
without a model call or application database, and saves reusable source bundles.
Pass the resulting `source-bundles.json` to each model with `--source-bundles`.
An explicit `--case-delay-seconds` between 0 and 60 can pace evaluation on Free
accounts; `--progress` prints public case IDs and safe statuses without prompts
or SDK exception bodies. A missing-evidence decline is reported separately from
schema success. Reports record safe provider settings, including output bounds
and reasoning mode. Frozen comparisons do not measure how future searches will rank.

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
