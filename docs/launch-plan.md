# Public beta launch plan

Target: quality-gated public beta, with no fixed date. The previous
18 September 2026 target has passed. Release candidate: `v2.0.0-beta.1`.
Authentication, data integrity, attribution, and recovery remain release gates.

## Product

SearchScribe is an open-source writing workspace for bloggers and creators.
The beta journey is topic → research → editable article → relevant photos →
SEO review → HTML or Markdown export. Users keep editorial control and can
restore saved versions.

The interface will use a warm, light editorial canvas with teal accents,
readable article typography, responsive navigation, accessible controls, and
an optional dark theme. Loading, empty, error, quota, and unsaved-edit states
must be designed alongside the successful flow.

## Delivery sequence

- [x] Reliability and security: transaction boundaries, pagination, session
  refresh, production settings, provider failures, and SQLite/Postgres CI.
- [x] Versioned editing: structured sections, SEO editing, conflict detection,
  and complete snapshots. Old versions must not invent historical metadata.
- [x] Next.js 16 and the responsive editorial workspace redesign (PRs #5–7).
- [ ] Public website: home, How it works, Features, Example, privacy, and
  password login at `/login` (implemented in draft PR #8; production pending).
- [ ] Google sign-in: verified stable provider identity, existing session flow,
  and explicit password-authenticated linking; never merge accounts by email.
- [ ] Live foundation: Vercel frontend, Render API, persistent Neon Postgres,
  migrations, and deployed signup/generation/edit/export verification.
- [ ] Research: bounded search, traceable source IDs, citations, and an explicit
  unresearched mode when search fails. Treat retrieved text as untrusted input.
- [ ] Photos: suggestions for a hero and relevant sections, user selection,
  photographer credits, source links, and editable alt text.
- [ ] AI routing: one combined article/SEO response, bounded fallback and
  deadline, persistent daily quotas, and idempotent generation requests.
- [ ] Production deployment, backup/restore rehearsal, accessibility and
  mobile verification, and release notes.

## Proposed free beta infrastructure

Keep the FastAPI modular monolith and Next.js frontend. Use Vercel Hobby only
for the noncommercial beta, Render Free for the API, and Neon Free for durable
Postgres. Free tiers have caps and cold starts; they are not unlimited hosting.
Verify account-specific eligibility and current terms before deployment.

Gemini is the proposed primary AI provider, with Groq as a bounded fallback.
Select actual model IDs only after checking account availability and evaluating
representative prompts. Tavily is the proposed research API and Pexels the photo
source. Configure keys in service secret stores, never the repository or chat.

Initial application limits: 3 generation/rewrite operations per user per day,
20 globally per day, reduced if provider allowances require it. Exhausting AI
quota must not prevent reading, manual editing, restoring, or exporting work.

## Release gates

- Green required CI on the PR's current commit; self-review before squash merge.
- Tests run against SQLite and an isolated Postgres service in GitHub Actions.
- No cross-user access or orphaned article content after deletion.
- Stale edits fail with a clear conflict response instead of overwriting work.
- Source links and photo credits survive exports and version restoration.
- At least 19 of 20 representative generation prompts pass schema validation;
  manually inspect factual attribution and photo relevance for the same set.
- Public website accurately describes shipped features and the complete journey.
- Password and Google signup/login, safe account linking, generation, editing,
  export, logout, and cold-start
  recovery work against the deployed API and persistent database.
- Backup restore and deployment rollback are rehearsed before tagging.

## Laptop isolation

Do not start, stop, restart, delete, prune, or reconfigure the maintainer's
office Docker resources. Run container and Postgres checks in GitHub Actions.
Local development uses this repository's existing virtual environment and
project dependencies, isolated test databases, and explicitly selected ports.
Do not change global Git/SSH configuration, install global packages, or use the
office GitHub identity for this personal repository.

## GitHub Flow

Branch from main, use Conventional Commits, push and open a PR early (draft
while incomplete). Run CI, review the final diff, squash merge only when green,
and delete merged branches. Tag a release only after the release gates pass.
Track remaining work in issues; do not describe planned features as shipped.

Uploads, generated imagery, CMS integrations, teams, billing, and video remain
outside this beta scope.
