import { expect, test } from "@playwright/test";

test("website and workspace navigation preserves the signed-in session", async ({
  page,
}) => {
  let refreshes = 0;
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/auth/refresh"))
      refreshes++;
  });
  const signedOut = page.waitForResponse(
    (response) => response.url().endsWith("/auth/refresh") && response.status() === 401,
  );
  await page.goto("/");
  await signedOut;
  for (const name of ["Features", "How it works", "Example"]) {
    await page
      .getByRole("navigation", { name: "Main navigation", exact: true })
      .getByRole("link", { name, exact: true })
      .click();
  }
  await page
    .getByRole("link", { name: "SearchScribe home", exact: true })
    .first()
    .click();
  expect(refreshes).toBe(1);
  await page.getByRole("link", { name: "Start writing", exact: true }).first().click();
  await page.getByLabel("Name").fill("Navigation Tester");
  await page.getByLabel("Email").fill(`navigation-${Date.now()}@test.dev`);
  await page.getByLabel("Password").fill("e2e-password-1");
  await page.getByRole("button", { name: /^Sign up$/ }).click();
  await expect(page.getByText("Hi, Navigation Tester")).toBeVisible({ timeout: 15_000 });

  await page.getByRole("link", { name: "Website", exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await page
    .locator("header")
    .getByRole("link", { name: "Account", exact: true })
    .click();
  await expect(page).toHaveURL(/\/account$/);
  await expect(
    page.getByRole("heading", { name: "Your account", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Website", exact: true }).click();
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
