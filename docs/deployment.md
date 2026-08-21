# Deployment

## Docker Compose (recommended)

```bash
docker compose up --build
```

- `postgres:16-alpine` with a named volume, `pg_isready` healthcheck
- `redis:7-alpine` (provisioned for future distributed limiter/caching)
- backend: multi-stage `python:3.12-slim`, non-root user, runs `alembic upgrade head` then uvicorn, container healthcheck against `/api/v1/health`
- frontend: multi-stage `node:20-alpine` → Next.js standalone server, non-root, healthcheck

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
