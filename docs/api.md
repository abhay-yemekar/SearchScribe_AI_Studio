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

| Method | Path                           | Auth                                | Notes                                                                                                |
| ------ | ------------------------------ | ----------------------------------- | ---------------------------------------------------------------------------------------------------- |
| POST   | `/auth/signup`                 | —                                   | 201, sets refresh cookie, returns access token + user. Rate-limited 10/min.                          |
| POST   | `/auth/login`                  | —                                   | 200, same shape as signup.                                                                           |
| POST   | `/auth/refresh`                | refresh cookie                      | Rotates the cookie, returns a fresh access token. 401 on expiry/reuse.                               |
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
| POST   | `/articles`                                 | Generate. Body `{"query": "..."}` (3–500 chars). 201 → detail. Rate-limited 5/min.                                                    |
| GET    | `/articles?limit=&cursor=`                  | Newest first; `next_cursor` present while more pages exist.                                                                           |
| GET    | `/articles/rewrite-styles`                  | Style registry for the rewrite picker.                                                                                                |
| GET    | `/articles/{id}`                            | Full detail.                                                                                                                          |
| PUT    | `/articles/{id}/content`                    | Save structured content + SEO as a new immutable version. Requires `base_version`; stale writes return `STALE_ARTICLE_VERSION` (409). |
| GET    | `/articles/{id}/photos?query=...`            | Owned article only. Explicit Commons photo search (3–120 characters), at most six suggestions, bounded network request, 10 searches/minute per user and client IP. |
| PUT    | `/articles/{id}/photos`                     | `{base_version, photos: [{id OR selection_token, section_id, alt}]}`. At most four images, one per cover/section; `section_id: null` selects the cover. Creates an immutable version and preserves SEO. |
| PATCH  | `/articles/{id}`                            | `{"title": "..."}` rename.                                                                                                            |
| DELETE | `/articles/{id}`                            | 204; cascades versions + SEO.                                                                                                         |
| POST   | `/articles/{id}/duplicate`                  | 201 copy with fresh versions.                                                                                                         |
| POST   | `/articles/{id}/rewrite`                    | `{"style": "genz\|professional\|casual\|technical\|marketing\|minimal"}` → new version.                                               |
| GET    | `/articles/{id}/versions`                   | Version list (version, change_type, word_count, complete_snapshot, created_at).                                                       |
| GET    | `/articles/{id}/versions/{version}`         | One version's markdown.                                                                                                               |
| POST   | `/articles/{id}/versions/{version}/restore` | Restores as a **new** version.                                                                                                        |

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
  "created_at": "2026-08-21T10:00:00",
  "updated_at": "2026-08-21T10:05:00"
}
```

## Health

- `GET /health` — liveness, `{"status": "ok"}`
- `GET /ready` — readiness; verifies DB connectivity, 503 when degraded.
