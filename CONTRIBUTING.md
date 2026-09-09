# Contributing to SearchScribe

Start with an issue describing the user problem and intended behavior. See
[the launch plan](docs/launch-plan.md) for beta scope and release gates.

## Workflow

1. Create a focused `feature/…`, `fix/…`, or `docs/…` branch from updated `main`.
2. Make Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`).
3. Push and open a pull request early; use a draft for unfinished work.
4. Run the relevant tests and wait for CI on the current PR commit.
5. Review the diff for regressions, secrets, debug output, and unrelated edits.
6. Squash merge when required checks pass, then delete the merged branch.

Never commit directly to main or merge with failing checks. Changes to database
schemas need an additive migration, tests, and a rollback/recovery explanation.
Preserve existing user content and migration history.

## Local checks

Use an isolated Python virtual environment and the frontend's local npm
dependencies. See [testing](docs/testing.md). No global dependency installation
is required. Unit tests use mock AI, so they should not spend provider credits.
Container and Postgres validation belong in GitHub Actions when developing on
a laptop with unrelated Docker workloads; do not alter those workloads.

Never commit `.env` files, tokens, production database contents, or private user
articles. Report vulnerabilities through the process in
[security](docs/security.md), without posting working credentials in an issue.

## Review evidence

Explain the trigger, the resulting behavior, and how it was tested. Include
screenshots for meaningful interface changes and label any tests not yet run.
Keep planned features distinct from shipped functionality in documentation.
