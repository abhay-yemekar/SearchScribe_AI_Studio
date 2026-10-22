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

Timestamps (`created_at`, `updated_at`) are UTC ISO 8601 with a `Z` suffix. `updated_at` changes with every new version.

Common codes: `VALIDATION_ERROR` (422), `AUTHENTICATION_REQUIRED` (401), `EMAIL_VERIFICATION_REQUIRED` (403), `NOT_FOUND` (404), `CONFLICT` (409), `PAYLOAD_TOO_LARGE` (413, bodies over 256 KiB), `RATE_LIMITED` (429), `GENERATION_FAILED` / `AI_PROVIDER_UNAVAILABLE` (502), `SERVICE_UNAVAILABLE` / `SERVER_BUSY` (503).

## Auth

| Method | Path                           | Auth                                | Notes                                                                                                |
| ------ | ------------------------------ | ----------------------------------- | ---------------------------------------------------------------------------------------------------- |
| POST   | `/auth/signup`                 | —                                   | 201, sets refresh cookie, returns access token + user. 10/min per client IP.                         |
| POST   | `/auth/login`                  | —                                   | 200, same shape as signup. 10/min per client IP; 10 attempts per email per 15 min.                   |
| POST   | `/auth/refresh`                | refresh cookie                      | Rotates the cookie, returns a fresh access token. 401 on expiry/reuse. Own limits.                   |
| POST   | `/auth/logout`                 | refresh cookie                      | Revokes the session, clears the cookie.                                                              |
| GET    | `/auth/me`                     | Bearer                              | Current user.                                                                                        |
| GET    | `/auth/password/add/challenge` | Bearer                              | Google-only account: five-minute, one-use identity challenge; sets a dedicated HttpOnly cookie.      |
| POST   | `/auth/password/add`           | Bearer + dedicated challenge cookie | Body `{credential, password}`. Confirms the already-linked Google identity before adding a password. |
| POST   | `/auth/password/change`        | Bearer                              | Body `{current_password, password}`. Confirms the current password before changing it.               |

Password mutations return `{message}`, clear session cookies, and invalidate all
access/refresh sessions and outstanding security tokens. Sign in again afterward.
The account, saved articles, and Google connection remain intact. New passwords
must contain a letter and digit and be 8–128 characters. These operations do not
return a password or automatically issue a new session.

`TokenOut`: `{access_token, token_type: "bearer", expires_in, user: {id, email, name, created_at}}`

## Articles

| Method | Path                                        | Notes                                                                                                                                 |
| ------ | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| POST   | `/articles`                                 | Generate. Body `{"query": "..."}` (3–500 chars). 201 → detail. 5/min per account. Production needs a verified email: else `403 EMAIL_VERIFICATION_REQUIRED`.                                                     |
| GET    | `/articles?limit=&cursor=`                  | Newest first; `next_cursor` present while more pages exist.                                                                           |
| GET    | `/articles/rewrite-styles`                  | Style registry for the rewrite picker.                                                                                                |
| GET    | `/articles/{id}`                            | Full detail.                                                                                                                          |
| PUT    | `/articles/{id}/content`                    | Save structured content + SEO as a new immutable version. Requires `base_version`; stale writes return `STALE_ARTICLE_VERSION` (409). |
| GET    | `/articles/{id}/photos?query=...`            | Owned article only. Explicit Commons photo search (3–120 characters), at most six suggestions, bounded network request, 10 searches/minute per user and client IP. |
| PUT    | `/articles/{id}/photos`                     | `{base_version, photos: [{id OR selection_token, section_id, alt}]}`. At most four images, one per cover/section; `section_id: null` selects the cover. Creates an immutable version and preserves SEO. |
| PATCH  | `/articles/{id}`                            | `{"title": "..."}` rename.                                                                                                            |
| DELETE | `/articles/{id}`                            | 204; cascades versions + SEO.                                                                                                         |
| POST   | `/articles/{id}/duplicate`                  | 201 copy with fresh versions.                                                                                                         |
| POST   | `/articles/{id}/rewrite`                    | `{"style": "genz\|professional\|casual\|technical\|marketing\|minimal"}` → new version. Same verified-email rule as generate.                                               |
| GET    | `/articles/{id}/versions`                   | Version list (version, change_type, word_count, complete_snapshot, created_at).                                                       |
| GET    | `/articles/{id}/versions/{version}`         | One version's markdown.                                                                                                               |
| POST   | `/articles/{id}/versions/{version}/restore` | Restores as a **new** version. Optional body `{base_version}`; stale returns `STALE_ARTICLE_VERSION` (409).                           |

`ArticleDetailOut`:

`content.photos` contains server-owned source metadata and editable alt/placement.
Search selections are signed for the authenticated owner and article and expire
after 30 minutes; they are not login tokens. Ordinary content saves cannot replace
photo credits or drop a cover photo. Removing a section removes its photo in the
new version; its previous snapshot remains restorable. Rewrite keeps photos and
their section positions, or rejects a layout change that would lose an image.
Only configured Commons raster hosts and supported Creative Commons/public-domain
license URLs are accepted. Search is disabled by `PHOTO_PROVIDER=disabled`.
No database migration is required: media lives in the version's content snapshot.

Deploy the compatible API before exposing the Photos UI where possible. After
photo snapshots exist, a pre-photo API cannot safely preserve media during text
edits: retain a known photo-aware rollback build, or suspend writes during rollback.

`seo.review_status` is server-owned: `generated`, `needs_review`, `edited`, or
`unknown` for legacy snapshots. It records provenance/review needs, not factual
verification. It survives reload, duplication and version restoration. Changing
article content marks retained SEO for review; changing SEO fields records an
editorial edit. Sending a status in a save request cannot promote it.

```json
{
  "id": 1,
  "title": "...",
  "query": "...",
  "status": "ready",
  "current_version": 2,
  "content": {
    "title": "...",
    "introduction": "...",
    "sections": [
      { "id": "...", "heading": "...", "paragraphs": ["..."], "bullets": [] }
    ],
    "conclusion": "..."
  },
  "markdown": "# Title ...",
  "html": "<!DOCTYPE html> ...",
  "seo": {
    "title": "...",
    "description": "...",
    "keywords": ["..."],
    "og_title": "...",
    "og_description": "...",
    "canonical_url": null,
    "robots": "index, follow",
    "review_status": "generated"
  },
  "created_at": "2026-08-21T10:00:00Z",
  "updated_at": "2026-08-21T10:05:00"
}
```

## Generation request recovery and daily limits

Send a fresh `Idempotency-Key` (16-64 ASCII letters, digits, `_` or `-`) on
article generation and rewrite POSTs. Reuse that key only to retrieve the same
logical action, never for a different topic/style. The accepted key is also
returned as `X-Generation-Request`. Legacy callers without a key receive a
server-generated one, but cannot recover a lost response without knowing it.

`GET /generation-requests/{key}` is authenticated and account-scoped. It returns
`processing`, `completed`, `failed` or `interrupted`, with a result article ID
and version when available. A completed replay returns the existing article's
current state; it does not create another article/version or call AI again.
Deleted results remain deleted. Failed/interrupted requests require an explicit
new key to try again; they are never automatically rerun. Completion and article
storage commit together. Expired operations cannot commit a late result.

Daily UTC reservations are stored in PostgreSQL/SQLite, shared across workers
and restarts. `GENERATION_DAILY_USER_LIMIT=3` and
`GENERATION_DAILY_GLOBAL_LIMIT=20` are configurable beta defaults. Each accepted
generation/rewrite attempt spends one slot, including provider failures and
clarification requests that used AI; model retries/SEO repair belong to that
same operation. Replays and rejected reservations do not spend extra slots.
`429 GENERATION_DAILY_LIMIT` includes `Retry-After` and an exact reset time.
Reading, manual edits, photos, restoration and exports do not consume these slots.
Mock preview/E2E launchers explicitly use larger limits for repeated QA.

The workspace keeps only the request identifier in tab session storage, without
credentials/topic/article text. After a lost response or reload, **Check previous
request** retrieves its saved result rather than silently generating again.
This is request recovery, not a background job queue or an exactly-once promise
from external AI providers. Apply migration `d84b_generation_operations` before
deploying this frontend. Leave the new tables in place during a code rollback;
older API builds do not enforce these reservations or deduplicate requests.

## Health

- `GET /health` — liveness, `{"status": "ok"}`
- `GET /ready` — readiness; verifies DB connectivity, 503 when degraded.
- `GET /version` — what is deployed: `{"git_sha", "alembic_head", "alembic_revision", "environment"}`. `alembic_head` is the newest migration in the code; `alembic_revision` is the one the database is on (`null` if it can't be read). They match after a good deploy. `git_sha` comes from `GIT_SHA` or Render's `RENDER_GIT_COMMIT`, else `"unknown"`.

Every response carries `X-Request-ID`, including an unexpected 500, whose body is the `INTERNAL_ERROR` envelope with the same `request_id`. Search the logs or Sentry for that ID.
