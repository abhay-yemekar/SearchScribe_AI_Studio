# Testing

## Backend — pytest (55 tests, fully offline)

```bash
cd backend && ../.venv/Scripts/python -m pytest
```

Layout: `tests/` with `conftest.py` providing an isolated in-memory SQLite per test (StaticPool), an API client with dependency overrides, and helpers (`register_user`, `generate_article`).

Coverage:

- **Health/middleware** — probes, request IDs, security headers, error envelope on unknown routes.
- **Migrations** — `alembic upgrade head` creates the full schema from scratch; downgrade drops it.
- **Auth** — signup/duplicate email/weak password, login success/failure, email normalization, `/me` with garbage tokens, refresh rotation + replay revocation, logout, brute-force rate limiting.
- **Security units** — Argon2id hash format + salts + constant-time verify, JWT round-trip, refresh-token randomness/hashing.
- **AI units** — mock provider round-trips, retry recovery/give-up/no-retry-on-permanent, schema rejection of empty sections, renderer XSS escaping, sanitizer script/event-handler/`javascript:` stripping, prompt registry errors, SEO normalization clamps.
- **Articles API** — generation detail, oversized query rejection, provider failure → 502 with **no partial rows**, transient-failure retry, cursor pagination, cross-user isolation (GET/PATCH/DELETE/rewrite/versions), rename/delete, duplicate, rewrite → version 2, unknown style, restore → version 3, generation rate limiting.

The AI provider is always the MockProvider in tests (`AI_PROVIDER=mock`); no network calls, deterministic, with failure-injection hooks.

## Frontend — Vitest + Testing Library (15 tests)

```bash
cd frontend && npm test
```

- **API client** — success path with Bearer header, error envelope → `ApiError` (code/request-id), non-JSON fallback, silent refresh + retry with the fresh token, refresh failure → `UnauthorizedError`, no refresh loop on auth endpoints.
- **ArticleView** — markdown → formatted HTML, script stripping, `javascript:` link neutralization, word count.
- **Tabs** — ARIA roles/selected state, panel switching, click and arrow-key navigation.

## E2E — Playwright

```bash
cd frontend && npx playwright test
```

Boots a real stack automatically (backend :8001 with mock AI + fresh SQLite via migrations, frontend :3100) and walks the full journey: signup → dashboard → generate → SEO tab → HTML preview (sandboxed iframe) → rewrite → versions → restore → logout → protected-route redirect.

## CI (GitHub Actions)

`backend` job: ruff → mypy → pytest. `frontend` job: eslint → tsc → vitest → build. `e2e` job runs the Playwright suite on Ubuntu. `docker` job builds both images. See [.github/workflows/ci.yml](../.github/workflows/ci.yml).
