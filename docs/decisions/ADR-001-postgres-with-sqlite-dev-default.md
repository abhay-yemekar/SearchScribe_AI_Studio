# ADR-001: PostgreSQL in production, SQLite as the zero-setup dev default

**Status:** Accepted

## Context

The project needs production-grade storage (transactions, concurrency, JSONB, operational tooling) while staying trivially runnable locally for evaluation and contribution.

## Decision

One SQLAlchemy 2.x + Alembic code path with two engines: SQLite by default for local dev/tests, PostgreSQL 16 via docker-compose for production-like runs. Dialect differences are isolated to connection args and one `JSON().with_variant(JSONB, ...)` column.

## Consequences

- ✅ Clone-and-run works with no database install; CI stays fast.
- ✅ Migrations are exercised against both engines (batch mode handles SQLite's ALTER limits).
- ⚠️ SQLite-specific behaviors (e.g. naive datetimes) must be managed centrally (`utc_now`).
- ⚠️ Rare SQL valid on one engine only would surface late; mitigated by keeping queries simple and testing the compose stack.

## Alternatives considered

- Postgres-only: more faithful, but blocks quick local evaluation behind Docker.
- Keeping the original `create_all`-on-import: no migration history, no schema evolution story — rejected outright.
