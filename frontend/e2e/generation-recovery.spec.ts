import { expect, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";

// Disposable local/CI mock stack only. The accepted POST reaches the real API;
// only its browser response is dropped to reproduce an ambiguous network failure.
for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
  test(`recovers a committed draft after a lost response and reload at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport);
    const signup = await page.request.post("/api/v1/auth/signup", { data: {
      name: "Recovery Test",
      email: `recovery-${viewport.width}-${Date.now()}@test.dev`,
      password: "local-recovery-password-1",
    } });
    expect(signup.status()).toBe(201);
    let posts = 0;
    let saved: { id: number; title: string } | undefined;
    await page.route("**/api/v1/articles", async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      posts++;
      expect(route.request().headers()["idempotency-key"]).toMatch(/^[\w-]{36}$/);
      const response = await route.fetch();
      expect(response.status()).toBe(201);
      saved = await response.json();
      await route.abort("failed");
    });
    await page.goto("/dashboard");
    await page.getByRole("textbox", { name: "Topic / search query" }).fill("A practical guide to balcony gardens");
    await page.getByRole("button", { name: "Generate", exact: true }).click();
    await expect(page.getByRole("button", { name: "Check previous request" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Generate", exact: true })).toBeDisabled();
    expect(saved).toBeDefined();
    await page.reload();
    await page.getByRole("button", { name: "Check previous request" }).click();
    await expect(page.getByRole("heading", { name: saved!.title, exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Edit article", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Generate", exact: true })).toBeEnabled();
    expect(posts).toBe(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const shots = path.resolve(__dirname, "../../.cache/generation-reliability");
    await mkdir(shots, { recursive: true });
    await page.screenshot({ path: path.join(shots, `recovered-${viewport.width}.png`), fullPage: true });
  });
}
