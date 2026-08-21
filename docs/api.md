# API Reference

Base URL: `/api/v1` · Interactive docs at `/docs` (non-production).

All errors share one envelope:

```json
{
  "error": {
    "code": "GENERATION_FAILED",
    "message": "Unable to generate content right now. Please try again shortly.",
    "request_id": "a1b2c3d4e5f6"
  }
}
```

Common codes: `VALIDATION_ERROR` (422), `AUTHENTICATION_REQUIRED` (401), `NOT_FOUND` (404), `CONFLICT` (409), `RATE_LIMITED` (429), `GENERATION_FAILED` / `AI_PROVIDER_UNAVAILABLE` (502), `SERVICE_UNAVAILABLE` (503).

## Auth

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| POST | `/auth/signup` | — | 201, sets refresh cookie, returns access token + user. Rate-limited 10/min. |
| POST | `/auth/login` | — | 200, same shape as signup. |
| POST | `/auth/refresh` | refresh cookie | Rotates the cookie, returns a fresh access token. 401 on expiry/reuse. |
| POST | `/auth/logout` | refresh cookie | Revokes the session, clears the cookie. |
| GET  | `/auth/me` | Bearer | Current user. |

`TokenOut`: `{access_token, token_type: "bearer", expires_in, user: {id, email, name, created_at}}`

## Articles

| Method | Path | Notes |
| --- | --- | --- |
| POST | `/articles` | Generate. Body `{"query": "..."}` (3–500 chars). 201 → detail. Rate-limited 5/min. |
| GET | `/articles?limit=&cursor=` | Newest first; `next_cursor` present while more pages exist. |
| GET | `/articles/rewrite-styles` | Style registry for the rewrite picker. |
| GET | `/articles/{id}` | Full detail. |
| PATCH | `/articles/{id}` | `{"title": "..."}` rename. |
| DELETE | `/articles/{id}` | 204; cascades versions + SEO. |
| POST | `/articles/{id}/duplicate` | 201 copy with fresh versions. |
| POST | `/articles/{id}/rewrite` | `{"style": "genz\|professional\|casual\|technical\|marketing\|minimal"}` → new version. |
| GET | `/articles/{id}/versions` | Version list (version, change_type, word_count, created_at). |
| GET | `/articles/{id}/versions/{version}` | One version's markdown. |
| POST | `/articles/{id}/versions/{version}/restore` | Restores as a **new** version. |

`ArticleDetailOut`:

```json
{
  "id": 1, "title": "...", "query": "...", "status": "ready",
  "current_version": 2,
  "markdown": "# Title ...",
  "html": "<!DOCTYPE html> ...",
  "seo": {"title": "...", "description": "...", "keywords": ["..."],
           "og_title": "...", "og_description": "...",
           "canonical_url": null, "robots": "index, follow"},
  "created_at": "2026-08-21T10:00:00", "updated_at": "2026-08-21T10:05:00"
}
```

## Health

- `GET /health` — liveness, `{"status": "ok"}`
- `GET /ready` — readiness; verifies DB connectivity, 503 when degraded.
