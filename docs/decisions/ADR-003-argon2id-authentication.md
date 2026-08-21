# ADR-003: Argon2id password hashing and rotating refresh-cookie sessions

**Status:** Accepted

## Context

The original implementation hashed passwords with unsalted SHA-256 and kept long-lived JWTs in `localStorage` — both disqualifying for production.

## Decision

- **Argon2id** (`argon2-cffi`, library defaults) with random salts; constant-time verification.
- **Sessions**: 15-minute access JWT held in client memory only + 256-bit opaque refresh token in an `HttpOnly`, `SameSite=Lax`, `Secure`-in-production cookie scoped to `/api/v1/auth`. Only a SHA-256 hash is stored server-side.
- **Rotation on every refresh**; presenting a revoked token revokes all of that user's sessions (theft response).
- Password policy: 8–128 chars, ≥1 letter, ≥1 digit; email normalized to lowercase.
- Rate limits on all auth endpoints (10/min/IP by default).

## Consequences

- ✅ XSS cannot exfiltrate the access token (not in storage) nor the refresh token (HttpOnly).
- ✅ Stolen refresh tokens become useless after one use and trigger session-wide revocation.
- ✅ Logout is server-side revocation, not just client cleanup.
- ⚠️ Silent-refresh handshake on app load adds one request; coalesced client-side to avoid storms.
- ⚠️ Cookie requires first-party context — solved by proxying `/api` through the Next.js server (ADR-005).

## Alternatives considered

- bcrypt: acceptable, but Argon2id is the current OWASP first recommendation and available via a maintained wheel.
- Longer-lived JWTs in localStorage: rejected (XSS exposure, no revocation).
