# Public beta launch plan

Target: quality-gated public beta, with no fixed date. The previous
18 September 2026 target has passed. Release candidate: `v2.0.0-beta.1`.
Authentication, data integrity, attribution, and recovery remain release gates.

## Product

SearchScribe is an open-source writing workspace for bloggers and creators.
The beta journey is topic → research → editable article → relevant photos →
SEO review → HTML or Markdown export. Users keep editorial control and can
restore saved versions.

The interface uses a warm editorial canvas, charcoal type and restrained accents,
readable article typography, responsive navigation, accessible controls, and
an optional dark theme. Loading, empty, error, quota, and unsaved-edit states
must be designed alongside the successful flow.

## Delivery sequence

- [x] Reliability and security: transaction boundaries, pagination, session
      refresh, production settings, provider failures, and SQLite/Postgres CI.
- [x] Versioned editing: structured sections, SEO editing, conflict detection,
      and complete snapshots. Old versions must not invent historical metadata.
- [x] Next.js 16 and the responsive editorial workspace redesign (PRs #5–7).
- [x] Public website: home, How it works, Features, Example, privacy, and
      password login at `/login` (PR #8 merged; live on searchscribe-ai.vercel.app).
- [x] Google sign-in implementation and deployment (PR #10): stable provider identity,
      existing session flow, and explicit password-authenticated linking; no email auto-merge.
- [ ] Real Google sign-in/session and account-linking acceptance on production.
- [x] Live foundation: Vercel frontend, Render API, persistent Neon Postgres,
      migrations, and deployed signup/generation/edit/export verification.
- [ ] Account recovery and email: forgot/reset password, verified email, safe
      transactional delivery, persistent send limits, and inbox verification.
      Setup instructions and sender constraints: [auth-setup.md](auth-setup.md).
      Recovery and password management shipped in PRs #16–20; real verification,
      Google-to-password addition and notice delivery are verified. Untracked
      direct links, full reset acceptance and mobile email rendering remain open.
      **Open provider blocker: Brevo ticket #5612282.** Its 12 October reply
      refuses tracking removal for new SMTP relay clients and offers a branded
      hostname that retains tracking. Clarify the HTTPS API behavior and inspect
      a delivered message before enabling direct security links. Keep manual-code
      delivery available. Authorized follow-up submitted 15 October 2026;
      Brevo confirmed receipt and reopened the ticket. Await its response.
      Include this item in every overall project status;
      see the support decision in [auth-setup.md](auth-setup.md).
- [x] Writing workflow: visible unsaved-edit status, keep/discard protection,
      in-memory draft retention across workspace navigation, and Markdown export
      from saved versions with source links and provenance.
- [x] Research: bounded search, traceable source IDs, citations, and an explicit
      unresearched mode when search fails. Treat retrieved text as untrusted input.
      Dynamic Tavily search replaces the topic-specific source catalog. It uses
      the actual query, one bounded basic search and saved source excerpts.
      Relative current-topic queries use dated recent coverage (default 30 days);
      undated and out-of-window results are excluded. Missing configuration,
      unavailable search and insufficient evidence have distinct errors.
      Source links and estimated dates survive versions, HTML and Markdown.
      Live provider acceptance verified in PR #22: the reported latest-tweet
      query generated a saved draft with five dated sources, including two
      direct X links. Reload and actual HTML preview retained the source snapshot.
      Source retrieval does not prove every claim or establish that a social post
      is the absolute latest. Broader factual evaluation remains a release gate.
- [x] Photos: suggestions for a hero and relevant sections, user selection,
      photographer credits, source links, and editable alt text.
      Released in PR #33 using keyless Wikimedia Commons
      search, server-owned metadata, signed selections, durable version snapshots
      and HTML/Markdown credits. Production API `f310f12` and frontend `24b453c`
      verified 15 October: real 7008×4672 photo selected on a separate article copy,
      version saved, full reload retained photo/alt/credits, HTML preview included
      attribution, and a 1280×853 preview loaded. Responsive fixture checks pass.
- [ ] AI routing: one combined article/SEO response, bounded fallback and
      deadline, persistent daily quotas, and idempotent generation requests.
      Combined generation and one targeted SEO repair are implemented. Saved
      review status distinguishes AI metadata, degraded/stale metadata, manual
      edits and legacy records. Deadline, quotas, provider routing and the broader
      prompt evaluation were the next phase. Request-scoped deadlines, optional
      configuration-driven Gemini/Groq fallback and a reusable 20-query evaluation
      harness are implemented; deployment and real fallback/model acceptance must
      be recorded separately. Persistent daily reservations, request idempotency
      and lost-response recovery shipped in PR #34 (API `556a7d9`, frontend
      `c96c88f`, migration `d84b_generation_operations`). Live reload recovered a
      terminal provider failure without generating again. A subsequent authorized
      live attempt recovered one saved Version 1 article after reload; processing
      and completed states, repeat reload and clean console were verified. Successful
      recovery also passes desktop/mobile local and CI tests. Final AI quality
      acceptance is separate from this request-integrity check.
- [ ] Production deployment, backup/restore rehearsal, accessibility and
      mobile verification, and release notes.

## QA priorities after the 9 October review

1. **P0 — Current facts and complete SEO.** Retrieve relevant current sources or
   decline unsupported timely drafts. Generate article and SEO together; attempt
   one repair if SEO is unsuitable. Preserve valid articles with editable text
   from the article and an explicit review status if repair fails. Saved articles are
   retained; these changes do not rewrite the user's previous drafts.
2. **P1 — Reliable navigation.** Preserve theme choices across public pages,
   provide distinct Account and Open workspace destinations, make interactive
   controls usable on their first enabled click, and fit normal login/signup
   forms on short desktop screens without clipping validation or zoomed content.
3. **P1 — Authentication acceptance and recovery.** Verify real Google login
   and explicit linking, then implement password recovery and transactional mail.
   Google's personalized button can still open an account chooser; that is
   Google's identity-selection flow, not evidence of failed SearchScribe login.
4. **P2 — Credited photos and visual enrichment.** Add relevant selectable photos
   with durable credits and alt text, then refine motion within reduced-motion
   and performance constraints. Keep the approved logo and editorial design.

Repeatable local QA is available through `$searchscribe-check`; mock tests do not
establish real Google consent, email delivery, AI accuracy or production persistence.

## Proposed free beta infrastructure

Keep the FastAPI modular monolith and Next.js frontend. Use Vercel Hobby only
for the noncommercial beta, Render Free for the API, and Neon Free for durable
Postgres. Free tiers have caps and cold starts; they are not unlimited hosting.
Verify account-specific eligibility and current terms before deployment.

Gemini is the proposed primary AI provider, with Groq as a bounded fallback.
Select actual model IDs only after checking account availability and evaluating
representative prompts. Tavily is the research API. Pexels paused new API-key
issuance in the maintainer's account on 15 October; use keyless Wikimedia Commons
for the photo phase. Review each file's attribution/license and additional
restrictions. Configure other provider keys in secret stores, never the repository
or chat.

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
