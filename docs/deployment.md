# Deployment

## Public beta topology

The Next.js website stays on Vercel. Its server-side `/api/*` rewrite forwards
to FastAPI on Render. FastAPI stores accounts and articles in persistent Neon
Postgres. Browser sessions remain first-party on the Vercel domain.

This is a proposed zero-spend, noncommercial beta, not an unlimited hosting
promise. Check account limits before launch: [Vercel Hobby policy](https://vercel.com/docs/limits/fair-use-guidelines),
[Render Free](https://render.com/docs/free), and [Neon plans](https://neon.com/pricing).
Render Free sleeps and its filesystem is ephemeral; production SQLite is refused.
The in-memory minute limiter is single-process and resets on restart. Persistent
daily generation reservations and request journals shipped in PR #34. Optional
provider fallback is implemented; writer quality qualification remains open.

### Reliability release — 15 October 2026

PR #34 merged as `c96c88f`. Render deployment `dep-db87igij9qps73bv7750`
is Live on reviewed API commit `556a7d9`; startup upgraded
`c73a_security_email_recovery` to `d84b_generation_operations`. Vercel's production
deployment of `c96c88f` succeeded. Existing accounts and articles remained readable.
During the first real reload test the Gemini writer returned three bounded 503
responses; the journal retained the failed request and recovery unlocked the UI
without another generation. One authorized subsequent attempt succeeded: reload
while generating showed the pending-request control, status lookup first reported
processing, and a later lookup opened the saved article without another Generate
click. Exactly one matching draft and Version 1 were present, another full reload
retained the article, and the Chrome console was clean. Desktop/mobile lost-response
recovery also passes local and CI mock integration. Production still explicitly
uses `gemini-2.5-flash`; a source-code default does not change that hosting override.

### Existing service audit — 7 October 2026

Vercel hosts `searchscribe-ai.vercel.app`; the old hostname redirects there. An existing personal Render
Free service at `searchscribe-ai-studio.onrender.com` is still on commit
`c2fbd7f`, with root `backend` and start command `uvicorn ... --port 8000`.
Its masked environment has legacy `SQLALCHEMY_DATABASE_URL` and
`GEMINI_MODEL_NAME`; current code reads `DATABASE_URL` and `AI_MODEL`.
The old database URL selects SQLite; its contents, live generation, and frontend
`BACKEND_URL` have not been verified. The existing service and environment remain
unchanged. An isolated Neon Free organization **SearchScribe Personal** and project
**searchscribe-beta** were created in AWS Singapore (Postgres 18). The database is
connected to the new `searchscribe-beta-api.onrender.com` API. The unrelated Hirelens organization is unchanged.

The new API uses production validation, migration-before-start, and Neon persistence.
Vercel Production has `BACKEND_URL=https://searchscribe-beta-api.onrender.com`.
Live browser and same-origin checks passed signup/login, real Gemini generation,
article/SEO editing, stale edit rejection, version restore, HTML download, refresh,
logout, and cross-user access denial. API data persisted when tested across the
restart workflow. A database backup restore and rollback rehearsal are still pending.
The legacy service's auto-deploy is Off; no legacy data was migrated or deleted.
The new API now tracks main with auto-deploy Off; reviewed releases deploy manually.

When changing the public domain, verify CORS_ORIGINS, metadataBase, sitemap,
canonical links, email-link origins, Google authorized JavaScript origins, the
old-domain redirect, and a deployed login-to-export journey together.

**Do not deploy current main over this service until the old database is
identified and any needed data is backed up.** A missing current database variable
would otherwise select local SQLite. Production settings now fail closed.

## Render + Neon setup

1. Create a personal Neon Free project for SearchScribe, in a nearby available
   region. Complete any account terms yourself. Use a dedicated app database and
   role. Keep credentials in hosting secret stores, never Git, screenshots, chat,
   build arguments, or public `NEXT_PUBLIC_*` variables.
2. Copy the direct Postgres connection string, preserving `sslmode=require`
   (or stronger certificate verification). Plain `postgres://` and `postgresql://`
   URLs are normalized to the installed `postgresql+psycopg` driver. Use a direct
   endpoint for this single-instance beta and its migrations.
3. Identify the old service's database before changing its environment. If it
   contains real data, back it up and plan an explicit transfer. Alembic creates
   schema; it does not transfer an old SQLite database or convert old data.
4. After green CI and review, configure an isolated beta Render service below.
   Keep the old SQLite service intact until its data has been backed up and any
   transfer is explicitly verified. The new API hostname must be recorded after
   provisioning; do not send beta writes to the old service.
   `render.yaml` is a reference for a **new** service, not an instruction to replace
   the existing one. Importing it can create a second service. Keep auto-deploy off
   during initial database setup and deploy a reviewed commit explicitly.

| Render setting | Value |
| --- | --- |
| Runtime / plan | Python / Free |
| Root / branch | `backend` / `main` after PR merge |
| Build | `pip install -r requirements.txt` |
| Start | `python -m app.start` |
| Health check | `/api/v1/ready` |
| `PYTHON_VERSION` | `3.12.11` (same minor version as CI) |
| `APP_ENV` | `production` |
| `DATABASE_URL` | Dedicated Neon direct URL with TLS |
| `SECRET_KEY` | Cryptographically random, at least 32 characters |
| `PROXY_SHARED_SECRET` | A second random value (32+ characters, not `SECRET_KEY`); the same value goes on Vercel |
| `CORS_ORIGINS` | `https://searchscribe-ai.vercel.app` |
| `AI_PROVIDER` | `gemini` |
| `AI_MODEL` | An available model verified with the account's actual limits |
| `GEMINI_API_KEY` | Personal project key in Render's secret environment |
| `TAVILY_API_KEY` | Personal Tavily Free search key; backend only, paid/PAYG disabled |
| `SENTRY_DSN` | Optional: the Sentry Python/FastAPI project's DSN; blank keeps error tracking off |

Generate a key privately with `secrets.token_urlsafe(48)`; do not copy an example
key. Changing the signing key invalidates existing sessions. Keep the old model
and database variables until their migration is verified, then remove obsolete
variables deliberately. `/docs` is disabled and refresh cookies are Secure in
production. Mock AI is refused in production.

The entrypoint applies Alembic migrations before serving, exits on migration
failure, and binds Render's `PORT` (default 8000 locally). Render Free does not
provide the paid pre-deploy step. Run one instance/worker; concurrent migration
runners require a separate migration job or lock before scaling.
See [Render Python versions](https://render.com/docs/python-version) and
[Blueprint settings](https://render.com/docs/blueprint-spec).

5. On Vercel, set server-only `BACKEND_URL` to the **new beta API's HTTPS URL**,
   then rebuild the frontend. The old `searchscribe-ai-studio.onrender.com` URL
   belongs to the untouched SQLite service.
   The rewrite is resolved at build time. Use an isolated API/database for preview
   environments; never point automated tests or mock generation at production.
6. Verify API `/api/v1/health` and `/api/v1/ready`, then the same URLs through
   the Vercel `/api` proxy. A Vercel Ready badge alone proves only frontend deploy.
7. Set the same `PROXY_SHARED_SECRET` on Render and on Vercel (Production,
   server-only, never `NEXT_PUBLIC_*`), then redeploy both. Render and Vercel
   both see only proxy addresses, so without it every visitor shares one
   rate-limit bucket. `frontend/proxy.ts` sends Vercel's `x-real-ip` as
   `X-Client-IP` with the secret, and the API trusts that header only when the
   secret matches (constant-time compare). Either side missing is safe: the API
   falls back to the peer address, the old shared-bucket behaviour. Rotate by
   changing both values together.
8. After every API deploy, open `/api/v1/version` through the Vercel proxy:
   `git_sha` must be the commit you deployed and `alembic_revision` must equal
   `alembic_head`. Render supplies the commit as `RENDER_GIT_COMMIT`.
9. Optional error tracking: create two Sentry projects, Python (FastAPI) for the
   API and Browser JavaScript for the web app. Put the first DSN in Render's
   `SENTRY_DSN` and the second in Vercel's `NEXT_PUBLIC_SENTRY_DSN`
   (Production), then redeploy both; the browser DSN is read at build time and
   also opens the CSP's `connect-src` to that origin. Blank values keep Sentry
   off. Each API event is tagged with the `request_id` the user saw.

## Deployed acceptance evidence

Record commit SHAs, migration head, timestamp, and outcome without secrets:

- Create a beta test account through the Vercel website; login and refresh.
- Generate with the real provider, edit article and SEO, rewrite, restore a
  version, export HTML, logout, then login again. Inspect cookie Secure/HttpOnly
  flags and cross-user ownership checks using two test accounts.
- Restart only this personal Render service. Confirm saved edits and versions
  persist. Test its cold start through Vercel and record any timeout.
- Confirm a failed database connection makes readiness fail and a failed
  migration prevents a new process from serving.
- Check rate limiting with the actual ingress. After step 7, 11 wrong logins
  for a made-up address from one network must end in 429 there, while another
  network (for example a phone on mobile data) can still sign in. A direct call
  to the Render URL with a made-up `X-Client-IP` and no secret must not change
  which bucket it uses. Uvicorn's `proxy_headers` stays off, and
  `X-Forwarded-For` is never trusted.

Google account linking, current-source generation, credited photos, and daily
quotas remain release gates even after this foundation passes. Markdown download
and unsaved-edit protection shipped in PR #21.

Tavily research is a separate reviewed API deployment. Saving its key without
deploying the integration does not enable search. Verify a fresh sourced article
on the deployed stack before claiming general research works. Free search limits
and persistent application budgets must be checked before public release.

## Backup restore and rollback rehearsal

Use an approved environment with PostgreSQL client tools already available;
do not install or operate office Docker resources. Backups contain private user
data: store them encrypted with restricted access, outside the public repository.

1. Before every migration, record the deployed code and Alembic head and take a
   custom-format `pg_dump` from the **direct** endpoint. Supply credentials using
   a protected PostgreSQL service/password file, not shell history or command-line
   URLs. Verify the dump with `pg_restore --list`.
2. Create a separate disposable Neon database/branch for restoration. Double-check
   its host and database name before running `pg_restore --no-owner --no-acl` into
   that empty target. Never restore over production for a rehearsal.
3. Point an isolated API at the restored target. Confirm schema revision, account
   and article counts, ownership, version contents, SEO, and export of a known
   test article. Record evidence and backup time; counts alone are insufficient.
4. Rehearse deploying the previous reviewed API commit against this isolated
   database. Code rollback does not roll back schema. Prefer backward-compatible
   additive migrations; do not blindly run `alembic downgrade` on real data.
5. If a destructive migration requires database recovery, stop writes using an
   agreed procedure, restore into a **new** target, validate, switch the API's
   database setting, and reconcile writes after the backup. State the possible
   data-loss window before production recovery.

Record successful restore and rollback separately. Neon plan-specific history
or recovery features are not a substitute for a demonstrated restore.

### Repeatable synthetic rehearsal

`.github/workflows/backup-restore.yml` runs an isolated PostgreSQL 18 service in
GitHub Actions, matching the production database's major version. It uses fictional
accounts and mock AI, with email, Google, research and external photo search disabled.
It never connects to Neon, reads production secrets, or operates local Docker.

The real API creates two accounts, an article with a credited photo, edited SEO,
five immutable versions, another user's private article, and completed/failed request
journals. Native PostgreSQL 18 `pg_dump --format=custom` and `pg_restore --list`
produce and inspect the archive. Restore uses a separate new empty database with
`--exit-on-error --single-transaction --no-owner --no-acl`.
See PostgreSQL's [pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html) and
[pg_restore](https://www.postgresql.org/docs/18/app-pgrestore.html) documentation.

Acceptance compares every table's columns and all row hashes before API activity,
then checks password login, ownership, every article version, SEO, photo credits,
HTML/Markdown, journal recovery/replay, and new account/article inserts to catch
sequence errors. A separate process loads the PR base's application code against
the restored schema and verifies login, owned reads and exports without downgrading
the database. This proves previous-code read compatibility, not a hosting rollback;
generation must be suspended during an actual rollback to code without journals.

The script refuses remote hosts, other database names, and non-test/non-mock runs.
Only hashes, fictional record IDs, schema revision and acceptance outcomes are
published as a seven-day artifact. The dump stays inside the ephemeral CI service.
This rehearsal does **not** establish that a real Neon backup is recoverable.
Production backup restoration, provider quality and full beta acceptance remain
separate release gates.

The initial rehearsal passed in GitHub Actions run `38697723869` on 15 October
2026: native PostgreSQL 18 dump/restore, complete row comparison, API integrity
and previous-code acceptance all succeeded. Inspect the PR's latest checks before
merging; this historical run does not validate later changes automatically.

## Local Docker Compose (optional)

```bash
docker compose up --build
```

- `postgres:16-alpine` with a named volume, `pg_isready` healthcheck
- `redis:7-alpine` (provisioned for future distributed limiter/caching)
- backend: multi-stage `python:3.12-slim`, non-root user, runs `alembic upgrade head` then uvicorn, container healthcheck against `/api/v1/health`
- frontend: multi-stage `node:24-alpine` → Next.js standalone server, non-root, healthcheck

Keyless demo: `AI_PROVIDER=mock docker compose up`.

Production values to supply: `APP_ENV=production` (disables `/docs`, sets `Secure` cookies), a strong `SECRET_KEY`, `GEMINI_API_KEY`, and your real `CORS_ORIGINS`.

## Standalone

Backend (any host with Python 3.12+):

```bash
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Frontend: `npm ci && npm run build && npm start` with `BACKEND_URL` pointing at the API (the Next.js server proxies `/api/*`, keeping cookies first-party).

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`): lint → typecheck → tests → E2E → Docker image builds on every push/PR. Extend with a deploy step (push images to a registry, update the compose/host) as needed.

## Production checklist

- [ ] `APP_ENV=production`, strong `SECRET_KEY`, real `CORS_ORIGINS`
- [ ] `GEMINI_API_KEY` set (or an alternative provider implemented)
- [ ] PostgreSQL with backups; migrations applied (container does this automatically)
- [ ] Same `PROXY_SHARED_SECRET` on the frontend and API so rate limits see the real client IP
- [ ] Log shipping for the JSON logs (`generation.*`, `auth.*`, `http.request` events)
- [ ] Multiple replicas → swap the in-memory rate limiter for the Redis backend
- [ ] Monitor `/api/v1/health` (liveness) and `/api/v1/ready` (readiness)
- [ ] `/api/v1/version` shows the deployed commit, and the database is on `alembic_head`
- [ ] Sentry DSNs set on the API and frontend, with an email alert for new issues
