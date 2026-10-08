import { expect, test } from "@playwright/test";

test("website and workspace navigation preserves the signed-in session", async ({
  page,
}) => {
  await page.goto("/login?mode=signup");
  await page.getByLabel("Name").fill("Navigation Tester");
  await page.getByLabel("Email").fill(`navigation-${Date.now()}@test.dev`);
  await page.getByLabel("Password").fill("e2e-password-1");
  await page.getByRole("button", { name: /^Sign up$/ }).click();
  await expect(page.getByText("Hi, Navigation Tester")).toBeVisible({ timeout: 15_000 });

  await page.getByRole("link", { name: "Website", exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await page
    .getByRole("link", { name: /open workspace/i })
    .first()
    .click();
  await expect(page.getByText("Hi, Navigation Tester")).toBeVisible();

  await page.getByRole("link", { name: "Account", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Your account", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Website", exact: true }).click();
  await page
    .getByRole("link", { name: /open workspace/i })
    .first()
    .click();
  await expect(page.getByText("Hi, Navigation Tester")).toBeVisible();

  await page.getByRole("link", { name: "SearchScribe home", exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await page
    .getByRole("link", { name: /open workspace/i })
    .first()
    .click();
  await page.getByRole("button", { name: /^Logout$/ }).click();
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login$/);
});
