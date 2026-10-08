#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const print = (message) => process.stdout.write(`${message}\n`);

const flags = new Set(process.argv.slice(2));
const allowed = new Set(["--dry-run", "--skip-build", "--help"]);
const unknown = [...flags].filter((flag) => !allowed.has(flag));
if (unknown.length) {
  console.error(`Unknown option: ${unknown.join(", ")}`);
  process.exit(2);
}
if (flags.has("--help")) {
  print("Usage: node frontend/scripts/check-marketing.mjs [--dry-run] [--skip-build]");
  print(
    "Runs existing frontend checks. E2E, backend, and deployed verification are separate.",
  );
  process.exit(0);
}

const frontend = fileURLToPath(new URL("..", import.meta.url));
const checks = ["lint", "build", "typecheck", "test"].filter(
  (check) => !(check === "build" && flags.has("--skip-build")),
);
print(`Frontend checks: ${checks.join(" → ")}`);
if (flags.has("--skip-build"))
  print("Build explicitly skipped; no build result will be claimed.");
if (flags.has("--dry-run")) {
  print("Dry run: no checks executed.");
  process.exit(0);
}

// Invoke npm through Node so Windows needs no shell or string-built command.
const candidates = [
  process.env.npm_execpath,
  join(dirname(process.execPath), "node_modules", "npm", "bin", "npm-cli.js"),
  join(
    dirname(process.execPath),
    "..",
    "lib",
    "node_modules",
    "npm",
    "bin",
    "npm-cli.js",
  ),
  "/usr/share/nodejs/npm/bin/npm-cli.js",
].filter((path) => path && basename(path) === "npm-cli.js" && existsSync(path));
const npmCli = candidates[0];
if (!npmCli) {
  console.error(
    "Cannot locate npm-cli.js for this Node runtime. Use a Node installation with npm.",
  );
  process.exit(1);
}

for (const check of checks) {
  print(`\nRunning npm run ${check}`);
  const result = spawnSync(process.execPath, [npmCli, "run", check], {
    cwd: frontend,
    stdio: "inherit",
  });
  if (result.error || result.signal || result.status !== 0) {
    console.error(
      `Frontend check failed: ${check}${result.error ? ` (${result.error.message})` : ""}`,
    );
    process.exit(result.status && result.status > 0 ? result.status : 1);
  }
}
print(
  "\nExisting frontend checks passed. This does not establish deployed or E2E readiness.",
);
