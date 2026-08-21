# ADR-002: LLM provider abstraction (protocol + factory)

**Status:** Accepted

## Context

The original code called the Gemini SDK directly from route logic with a module-level client, silently replacing failures with fake content. The product must survive provider outages, provider switches, and must be testable without network or API keys.

## Decision

All LLM access goes through an `LLMProvider` Protocol returning Pydantic-validated models plus usage metadata. `GeminiProvider` (google-genai, structured output, timeouts) and `MockProvider` (deterministic, offline, failure-injection hooks) are the initial implementations; `get_provider()` selects by configuration. A typed error taxonomy (`Transient`/`Permanent`/`SchemaValidation`) drives a bounded retry with backoff + jitter for transient errors only.

## Consequences

- ✅ Adding OpenAI/Groq/local models = one file + one factory entry + env vars.
- ✅ The entire test suite (and keyless local dev) runs against the mock.
- ✅ Token usage, latency, prompt version, and status are recorded per call for cost/observability.
- ⚠️ One indirection layer to learn; kept minimal (a single `generate` method).

## Alternatives considered

- Direct SDK calls per endpoint: simplest, but couples business logic to one vendor and makes offline testing impossible.
- LangChain-style agent framework: heavy, unnecessary for two structured calls per generation.
