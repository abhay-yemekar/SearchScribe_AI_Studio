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
daily quotas and provider fallback remain separate launch work.

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
| `CORS_ORIGINS` | `https://searchscribe-ai.vercel.app` |
| `AI_PROVIDER` | `gemini` |
| `AI_MODEL` | An available model verified with the account's actual limits |
| `GEMINI_API_KEY` | Personal project key in Render's secret environment |

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
- Check rate limiting with the actual ingress. The entrypoint does not trust
  arbitrary forwarded IP headers; proxy traffic may share a minute-limit bucket.
  Configure and test a trusted ingress design before widening those limits.

Google sign-in, research citations, credited photos, Markdown export, and daily
quotas remain release gates even after this foundation passes.

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
- [ ] Reverse proxy terminating TLS; trust `X-Forwarded-For` there for correct rate-limit keys
- [ ] Log shipping for the JSON logs (`generation.*`, `auth.*`, `http.request` events)
- [ ] Multiple replicas → swap the in-memory rate limiter for the Redis backend
- [ ] Monitor `/api/v1/health` (liveness) and `/api/v1/ready` (readiness)
