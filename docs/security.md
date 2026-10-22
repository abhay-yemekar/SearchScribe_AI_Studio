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

- **API:** `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `X-Frame-Options: DENY`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`. `Cache-Control: no-store` on `/auth/*` responses and on every request with a bearer token, so a proxy or browser never caches tokens or private drafts.
- **Pages** (`frontend/lib/security-headers.mjs`): every page sends `nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: DENY` and `Permissions-Policy`. Every page has a CSP with `frame-ancestors 'none'`, `object-src 'none'`, `base-uri 'self'` and `form-action 'self'`, and allows only Google sign-in (`accounts.google.com/gsi/`) and Wikimedia images as outside origins.
  - App pages (`/dashboard`, `/account`, `/login` and the recovery pages) get a per-request nonce from `proxy.ts`: only scripts Next.js signs, and scripts those load (`'strict-dynamic'`), can run. These pages render dynamically for that reason.
  - Public marketing pages stay static, with a fixed CSP that allows inline scripts; they show no user content.
  - Styles allow inline for the sandboxed HTML preview and Google's button. Zod runs `jitless`, so its `eval` probe doesn't report a violation.
  - With `NEXT_PUBLIC_SENTRY_DSN` set, `connect-src` also allows that DSN's ingest origin (https only), so the browser can send error reports.
- CORS origins come from `CORS_ORIGINS` env, never hardcoded.

## Secrets

- `.env` is gitignored; `.env.example` documents every variable with placeholders.
- Production refuses to boot with the default `SECRET_KEY`.
- Logs never contain passwords, tokens, or API keys; errors returned to clients carry codes and request IDs, never stack traces or provider details.

## Error tracking

Sentry is optional and off unless a DSN is set (`SENTRY_DSN` on the API, `NEXT_PUBLIC_SENTRY_DSN` on the frontend). Both send errors only: no performance tracing and no session replay.

- **API:** `send_default_pii` is off, request bodies are never attached, and stack frames carry no local variables. That last one matters: frame locals hold the raw ASGI scope, whose headers include the bearer token and refresh cookie, and Sentry's scrubber doesn't filter them there. A test sends a real crash through the SDK and checks neither appears. Each event is tagged with the request's `request_id`, which is also in the 500 response and the JSON logs.
- **Browser:** user info, cookies, headers and HTTP bodies are off. The SDK records page URLs on events and navigation breadcrumbs without filtering, and reset and verification links carry their token in the fragment, so `lib/sentry.ts` strips the query and fragment from every reported URL. `app/global-error.tsx` reports a crashed root layout and shows a plain retry page.
- The browser DSN is public by design: it only lets a browser submit events to that project.

## Remaining known trade-offs

- The rate limiter is per-process (fine for single-worker deployments; swap to Redis when scaling horizontally).
- No email verification / password reset flow yet (roadmap).
- Without `PROXY_SHARED_SECRET` on both the frontend and API, every visitor behind Vercel shares the proxy's per-IP buckets.
- The per-email sign-in budget lets someone who knows an address block password sign-in for it for up to 15 minutes; Google sign-in and password reset still work.
