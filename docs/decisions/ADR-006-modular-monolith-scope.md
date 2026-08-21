# ADR-006: Modular monolith, explicitly deferred infrastructure

**Status:** Accepted

## Context

The rebuild brief allows ambitious architecture (queues, Redis-everything, agents, microservices). The actual workload is two short LLM calls per user action with synchronous UX expectations.

## Decision

Single FastAPI app with layered internals (routers → services → repositories, plus the AI package). Deliberately **not** introduced: message brokers, background workers, Kubernetes, agent frameworks, vector stores. Redis is provisioned in compose but unused by code (reserved for the distributed rate limiter when replicas > 1). Long generations can later move behind a queue without changing routes or services (`status=generating` field already exists).

## Consequences

- ✅ One deployable, simple debugging, fast CI, low hosting cost.
- ✅ Boundaries (provider protocol, service layer, repository layer) mark the exact seams for future extraction.
- ⚠️ Synchronous generation holds a worker for the LLM duration; acceptable at current scale, mitigated by timeouts + retries and the documented queue path.

## Alternatives considered

- Celery/Arq workers from day one: operational overhead with no user-visible benefit yet.
- Microservices per feature: distribution costs dominate at this size.
