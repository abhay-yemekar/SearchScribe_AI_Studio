# ADR-005: Access token in memory + refresh cookie over a same-origin proxy

**Status:** Accepted

## Context

Refresh cookies with `SameSite=Lax` are not sent on cross-site POSTs, and `SameSite=None` requires HTTPS (awkward in local dev). The frontend (:3000) and backend (:8000) are separate processes in development.

## Decision

The Next.js server proxies `/api/*` to the backend via rewrites (`next.config.mjs`, `BACKEND_URL`). The browser only ever sees same-origin requests, so `SameSite=Lax` works everywhere, CORS becomes irrelevant for the app flow, and the backend CORS list is only needed for direct API access (docs, curl).

## Consequences

- ✅ Cookie-based refresh works identically in dev and production.
- ✅ No CSRF tokens needed for the API: mutating calls require a Bearer header a cross-site form cannot set.
- ⚠️ One extra hop through the Next.js server; negligible for this workload.
- ⚠️ Frontend deployments must set `BACKEND_URL` (build arg + runtime env in the Dockerfile).

## Alternatives considered

- Bearer-only auth with localStorage: reintroduces XSS token theft; rejected.
- SameSite=None cookies: forces HTTPS locally and weakens default protections.
