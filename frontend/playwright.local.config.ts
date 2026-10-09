import { defineConfig } from "@playwright/test";

const localUrl = new URL(
  process.env.SEARCHSCRIBE_E2E_BASE_URL || "http://localhost:3200",
);
if (
  !["http:", "https:"].includes(localUrl.protocol) ||
  !["localhost", "127.0.0.1", "[::1]"].includes(localUrl.hostname) ||
  localUrl.username ||
  localUrl.password ||
  localUrl.pathname !== "/" ||
  localUrl.search ||
  localUrl.hash
) {
  throw new Error(
    "SEARCHSCRIBE_E2E_BASE_URL must be a loopback HTTP(S) origin without credentials, a path, query, or fragment.",
  );
}

// Use an already verified SearchScribe preview. This config starts no servers.
// Confirm mock AI and an isolated local database before tests that write data.
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  workers: 1,
  retries: 0,
  use: {
    baseURL: localUrl.origin,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});
