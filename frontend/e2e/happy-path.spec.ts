import { expect, test } from "@playwright/test";

const uniqueEmail = () => `e2e-${Date.now()}-${Math.floor(Math.random() * 10000)}@test.dev`;

test.describe("SearchScribe happy path (mock AI provider)", () => {
  test("signup -> generate -> rewrite -> versions -> restore -> logout", async ({
    page,
  }) => {
    const email = uniqueEmail();

    // --- Landing / signup ---
    await page.goto("/");
    await page.getByRole("button", { name: /sign up/i }).click();
    await page.getByLabel("Name").fill("E2E Tester");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("e2e-password-1");
    await page.getByRole("button", { name: /^Sign up$/ }).click();

    // --- Dashboard (session restored via refresh cookie) ---
    await expect(page.getByText("Hi, E2E Tester")).toBeVisible({ timeout: 15_000 });

    // --- Generate ---
    await page.getByLabel("Topic / search query").fill("Weekend trips from Pune");
    await page.getByRole("button", { name: /generate/i }).click();
    await expect(page.getByRole("heading", { name: /practical guide/i })).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText(/words/)).toBeVisible();

    // --- SEO tab ---
    await page.getByRole("tab", { name: /seo metadata/i }).click();
    await expect(page.getByText(/SEO Title/i)).toBeVisible();
    await expect(page.getByText(/Keywords/i)).toBeVisible();

    // --- HTML preview tab ---
    await page.getByRole("tab", { name: /html preview/i }).click();
    await expect(page.frameLocator("iframe").getByRole("heading", { level: 1 }).first()).toBeVisible();

    // --- Rewrite ---
    await page.getByRole("button", { name: /^Rewrite$/ }).click();
    await expect(page.getByText("Rewriting…")).toBeVisible();
    await page.getByRole("tab", { name: /versions/i }).click();
    await expect(page.getByText("Version 2")).toBeVisible({ timeout: 30_000 });

    // --- Restore version 1 ---
    await page
      .getByRole("listitem")
      .filter({ hasText: "Version 1" })
      .getByRole("button", { name: /restore/i })
      .click();
    await expect(page.getByText("Version 3")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/Restored/)).toBeVisible();

    // --- Logout ---
    await page.getByRole("button", { name: /logout/i }).click();
    await expect(page.getByRole("heading", { name: /welcome to/i })).toBeVisible({
      timeout: 15_000,
    });

    // Dashboard is protected after logout.
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: /welcome to/i })).toBeVisible({
      timeout: 15_000,
    });
  });
});
