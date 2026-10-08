# SearchScribe delivery automation

Run the existing frontend checks in their required order:

```powershell
node frontend/scripts/check-marketing.mjs
```

The helper runs lint, build, typecheck, and unit tests sequentially and returns the first failing exit code. Build precedes typecheck so Next.js route types are regenerated. It uses installed project dependencies; it does not install packages, deploy, change Git, or touch Docker.

Use `--dry-run` to inspect the schedule without running checks. Use `--skip-build` only when deliberately relying on a separately recorded build result; it explicitly reports the omission. Backend, Playwright, accessibility, and deployed acceptance checks remain separate and must be chosen for the actual change.

The personal `$searchscribe-release` Codex skill supplies project-specific release guidance: personal-account separation, honest feature/deployment evidence, public-site/workspace navigation, and a tested checkpoint before either account usage window reaches 85%. A skill is reusable guidance, not a scheduled job or permission to publish.

## Run the current local project

Ask Codex to use **`$runapp`** to start and open the current SearchScribe checkout. This is a skill invocation, not a promise of a custom `/runapp` slash-menu command. [Official skill invocation](https://learn.chatgpt.com/docs/build-skills).

The same project helper works directly from the repository root with PowerShell 7.4 or newer:

```powershell
pwsh -NoProfile -File frontend/scripts/runapp.ps1
```

It starts the API on port **8250** and the website at **http://localhost:3200**, then checks API, same-origin proxy, and homepage readiness before opening the default browser. Fresh starts use mock AI and `backend/codex_runapp_preview.db`; Google is disabled and no Gemini credits are spent. Existing servers are reused only when their process command lines belong to this checkout; their settings remain unchanged and are reported as unconfirmed. Office processes are never killed or reconfigured.

Use `-NoBrowser` when Codex will open Chrome itself, `-StatusOnly -NoBrowser` for inspection without starting anything, or `-DryRun` for a plan without file/process changes. Alternative `-ApiPort` and `-WebPort` values are explicit; avoid a second Next.js dev server against the same checkout. Logs and recorded project PIDs live in `.cache/runapp`. Dependencies must already be installed; the helper does not edit `.env`, install software, switch branches, deploy, or manipulate Docker.
