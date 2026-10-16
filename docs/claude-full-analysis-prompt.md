# Prompt: complete SearchScribe product and code analysis

Paste everything below the line into Claude Code, started in the repository root.
Paste the latest plan from another tool where shown, or delete that block.

---

You are the principal engineer, security reviewer, AI-systems engineer and product
lead for **SearchScribe AI Studio**, reviewing it before the next phase of work.

- Repository: this working directory (GitHub: `abhay-yemekar/SearchScribe_AI_Studio`)
- Live product: https://searchscribe-ai.vercel.app/ (Vercel → Render API → Neon Postgres;
  Gemini/Groq models, Tavily research, Wikimedia Commons photos, Resend email)
- Stack: Next.js 16 / React 19 / TanStack Query frontend in `frontend/`; FastAPI /
  SQLAlchemy 2 / Alembic backend in `backend/`; docs and status in `docs/`
- Audience: bloggers and creators who want a researched, editable first draft with
  SEO, photos, versions and export. Free, noncommercial beta built by one developer.

## Ground rules

1. **Read-only.** Do not edit application code, commit, push, deploy, change
   provider/hosting settings, send email, or create/delete real accounts. Do not
   generate articles on production (it spends the shared daily quota). Keep unrelated
   uncommitted changes in the working tree untouched.
2. **Evidence over opinion.** Every finding needs `file:line` (or URL plus observed
   response), a concrete failure scenario, severity and a specific fix. Read the
   code before reporting; label anything you could not confirm "unverified".
3. **Run the real checks** and report actual results, not assumptions:
   backend `ruff`, `mypy app`, `pytest`; frontend `npm run lint`, `npm run typecheck`,
   `npx vitest run`. Skip Playwright unless it is quick and isolated.
4. **Check the live site without logging in:** page timings, security headers on
   HTML and `/api/*` responses, public copy versus shipped features, robots/sitemap,
   404s for promised pages, console errors, mobile width and both themes.
5. **Docs are claims, not facts.** Compare README, `docs/*.md` and the public pages
   with the code; list every stale or contradictory statement.

## Work method

Fan out parallel read-only review agents, one per area below, then verify the most
severe findings yourself before reporting them:

| Area | What to cover |
| --- | --- |
| Security and accounts | Tokens, refresh rotation/replay, session invalidation, password policy and reuse, reset tokens, Google ID-token checks, account linking, enumeration, rate limits (per process or shared?), CSRF/cookies, CORS, CSP and headers, XSS in generated/exported HTML, SSRF, IDOR, input size limits, dependency CVEs |
| AI pipeline | Request flow (plan → search → evidence → draft → SEO → review/repair), timeouts versus proxy limits, retries/fallback/quota, idempotency and interrupted-request recovery, prompt injection from web pages, citation integrity, freshness for "latest" topics, Hindi/Hinglish, cost and calls per article, streaming, observability, model choice on free tiers, evaluation harness |
| Backend and data | API consistency, error envelope, pagination, optimistic concurrency, transactions, indexes and N+1s, pooling for Neon, cold starts, migrations, schema fit for search/sort, rename/duplicate/delete, export, account deletion, feedback, terms acceptance, briefs/outlines; test coverage gaps |
| Frontend and UX | Component size and boundaries, client versus server components, data fetching waterfalls, auth/session restore, theme consistency across every route, editor save/conflict races, unsaved-edit protection, loading/empty/error states, accessibility, mobile, copy quality |
| Delivery | CI coverage and gaps (security scanning, coverage, required checks), deploy/migration/rollback, backups, monitoring/alerting/error tracking, staging, repo hygiene, docs accuracy, release/versioning, process weight for a solo developer |
| Product and market | Positioning versus Jasper, Copy.ai, Frase, Surfer, Koala, Align and ChatGPT/Claude/Gemini themselves; what makes a user choose and return; activation, retention and trust; what to stop building |

## Plan to critique

Critique this plan line by line: what is right, wrong, stale against the code,
missing, over-engineered, or wrongly ordered. Do not copy it; replace it where a
better plan exists.

```
<PASTE THE OTHER PLAN HERE, OR DELETE THIS BLOCK>
```

## Deliverables

Write one Markdown report in `docs/` (that is the only file you create) and give
a short summary in chat. The report contains:

1. **Executive summary:** where the product stands in ten lines, and the three
   decisions that matter most.
2. **Scorecard (0–10):** security, AI quality, backend, frontend, UX, accessibility,
   tests, CI/CD, operations, docs, product differentiation. One line of justification each.
3. **Verified findings table:** ID, severity (Critical/High/Medium/Low), area,
   `file:line`, problem, failure scenario, fix, effort (S/M/L). Most severe first.
4. **Stale or false claims:** docs and public-site statements that disagree with the code.
5. **Plan critique:** agree / change / add / drop, with reasons.
6. **Recommended roadmap:** phases ordered by user and risk impact, each with goal,
   scope, explicit non-goals, acceptance evidence and an S/M/L estimate. Separate
   "fix the foundation", "make the core loop excellent" and "differentiate".
7. **Product strategy:** target user, the core promise, the north-star metric, the
   few features that create a reason to choose SearchScribe, and what to cut.
8. **First two weeks:** a concrete ordered list of small PRs, each shippable alone.

Reply to me in Hinglish; write the report in English.
