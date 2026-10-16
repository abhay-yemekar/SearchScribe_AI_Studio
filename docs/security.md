# Security

## Authentication

**Passwords** — Argon2id (`argon2-cffi`, library-default parameters: 64 MiB, t=3, p=4) with per-hash random salts. Password policy: 8–128 chars, at least one letter and one digit. The original unsalted SHA-256 hashing is gone.

**Session model**

- Access token: 15-minute JWT (HS256), `sub=user_id`, `type=access`. Held **in memory only** on the client — never in localStorage/sessionStorage/cookies.
- Refresh token: 256-bit opaque random value delivered in an `HttpOnly`, `SameSite=Lax`, `Secure`-in-production cookie scoped to `path=/api/v1/auth`. Only its SHA-256 hash is stored server-side.
- Rotation: every refresh revokes the presented token and issues a new one.
- Theft detection: presenting an already-revoked token revokes **every session** for that user.
- Logout revokes the session server-side and clears the cookie.

Same-origin note: the Next.js server proxies `/api/*` to the backend, so the cookie is always first-party and `SameSite=Lax` is sufficient — no cross-site POST problem, no CSRF token needed for the API (non-GET API calls additionally require the Bearer header, which cross-site forms cannot set).

## Authorization

Every article/versions query filters by `user_id` at the repository layer; services enforce ownership (`_require_article`). Cross-user access returns 404 (not 403) to avoid resource enumeration. Verified by tests that attempt GET/PATCH/DELETE/rewrite as another user.

## HTML safety

Three independent layers:

1. The LLM returns **structured JSON, never HTML**; the Jinja2 renderer autoescapes all interpolated values.
2. `sanitize_document` (nh3) strips scripts, event handlers, `javascript:` URLs, and unknown tags from the body before storage/serve.
3. The preview iframe runs with `sandbox=""` (no scripts, no same-origin access). Frontend markdown rendering passes through DOMPurify.

## Rate limiting

Sliding windows per minute (`RATE_LIMIT_*` env), each keyed so one caller can't use up another's budget:

- Signup, login and Google sign-in: 10 per client IP.
- `/auth/refresh`: 30 per refresh cookie value (its hash, or the client IP without one), within 120 per client IP. It has its own buckets, so page-load refreshes never spend the login budget. The cookie rotates on every successful refresh, so the per-cookie bucket mainly stops replayed or guessed values.
- Generate and rewrite: 5 per account. Photo search: 10 per account. Photo save: 20 per account.

The client IP is the connecting peer's, except that `X-Client-IP` from `frontend/proxy.ts` is used when it arrives with a matching `PROXY_SHARED_SECRET` (constant-time compare). `X-Forwarded-For` and uvicorn's `proxy_headers` are never trusted.

These are in-memory; the interface supports a Redis backend for multi-replica deployments (Redis is provisioned in compose). Persistent database buckets back the abuse controls that must survive restarts: 10 sign-in attempts per email address per 15 minutes (unknown addresses too, so a 429 reveals nothing; a successful sign-in resets it), and the hourly security-email and password-management budgets.

## Headers & CORS

- `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `X-Frame-Options: DENY`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`, `Cache-Control: no-store` on auth responses.
- CORS origins come from `CORS_ORIGINS` env, never hardcoded.

## Secrets

- `.env` is gitignored; `.env.example` documents every variable with placeholders.
- Production refuses to boot with the default `SECRET_KEY`.
- Logs never contain passwords, tokens, or API keys; errors returned to clients carry codes and request IDs, never stack traces or provider details.

## Remaining known trade-offs

- The rate limiter is per-process (fine for single-worker deployments; swap to Redis when scaling horizontally).
- No email verification / password reset flow yet (roadmap).
- Without `PROXY_SHARED_SECRET` on both the frontend and API, every visitor behind Vercel shares the proxy's per-IP buckets.
- The per-email sign-in budget lets someone who knows an address block password sign-in for it for up to 15 minutes; Google sign-in and password reset still work.
