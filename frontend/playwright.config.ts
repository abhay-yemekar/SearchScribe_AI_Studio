import { defineConfig } from "@playwright/test";

/**
 * E2E tests run against a real local stack:
 *  - backend on :8001 with AI_PROVIDER=mock and a throwaway SQLite database
 *  - frontend on :3100 proxying /api to the backend
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: "http://127.0.0.1:3100",
    trace: "on-first-retry",
  },
  webServer: [
    {
      command: "bash e2e/start-backend.sh",
      port: 8001,
      reuseExistingServer: false,
      timeout: 90_000,
    },
    {
      command: "npm run dev -- --port 3100",
      port: 3100,
      env: { BACKEND_URL: "http://127.0.0.1:8001" },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
