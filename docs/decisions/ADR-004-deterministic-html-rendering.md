# ADR-004: Deterministic HTML rendering from structured LLM output

**Status:** Accepted

## Context

The original design asked the LLM for arbitrary HTML strings and served them as-is (preview, download, storage) — an XSS-prone, unvalidatable contract.

## Decision

The LLM returns a **structured article JSON** (title / introduction / sections{heading, paragraphs, bullets} / conclusion), validated by Pydantic. A deterministic Jinja2 template (autoescape on) renders Markdown and the standalone HTML page; `nh3` sanitizes the body as defense in depth; the preview iframe is fully sandboxed; the frontend additionally sanitizes markdown rendering through DOMPurify.

## Consequences

- ✅ XSS is structurally difficult: the model never authors markup.
- ✅ Output is stable and testable; renderer/sanitizer have dedicated unit tests with malicious payloads.
- ✅ SEO metadata is generated in a separate pass and clamped by deterministic rules (title ≤ 60, description ≤ 160).
- ✅ One canonical representation (structured JSON in `article_versions`) — Markdown and HTML are derived, never duplicated.
- ⚠️ Rich layouts the old "arbitrary HTML" mode could produce are gone by design; extensions go through schema + template changes.

## Alternatives considered

- Sanitizing LLM-generated HTML directly: weaker guarantee (sanitizer bypasses exist) and no output contract.
