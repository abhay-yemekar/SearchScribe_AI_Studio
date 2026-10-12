import { expect, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";

// Disposable accounts in the isolated mock-provider stack; never production users.
const initialPassword = "local-password-1";
const nextPassword = "local-password-2";
const apiOrigin = process.env.E2E_API_URL ?? "";
if (apiOrigin && !/^http:\/\/127\.0\.0\.1:\d+$/.test(apiOrigin)) {
  throw new Error("E2E_API_URL must be an isolated loopback API.");
}
const apiPath = (pathname: string) => `${apiOrigin}${pathname}`;

test.beforeEach(async ({ page }) => {
  // Windows checks reuse the project's dev frontend while isolating API data.
  if (apiOrigin) {
    await page.route("**/api/v1/**", async (route) => {
      const url = new URL(route.request().url());
      const response = await route.fetch({
        url: `${apiOrigin}${url.pathname}${url.search}`,
      });
      await route.fulfill({ response });
    });
  }
});

for (const viewport of [
  { width: 1422, height: 900 },
  { width: 390, height: 844 },
]) {
  test(`change password revokes sessions and preserves articles at ${viewport.width}px`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    const email = `password-${Date.now()}-${viewport.width}@test.dev`;
    const signup = await page.request.post(apiPath("/api/v1/auth/signup"), {
      data: { name: "Password Test", email, password: initialPassword },
    });
    expect(signup.status()).toBe(201);
    const account = await signup.json();
    const oldAuthorization = { Authorization: `Bearer ${account.access_token}` };
    const generated = await page.request.post(apiPath("/api/v1/articles"), {
      headers: oldAuthorization,
      data: { query: "Growing herbs on a balcony" },
    });
    expect(generated.status()).toBe(201);
    const article = await generated.json();

    await page.goto("/account");
    const passwordSection = page.getByRole("region", {
      name: "Change password",
      exact: true,
    });
    await expect(passwordSection).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Website", exact: true }),
    ).toHaveAttribute("href", "/");
    const dimensions = await page.evaluate(() => ({
      width: window.innerWidth,
      content: document.documentElement.scrollWidth,
    }));
    expect(dimensions.width).toBe(viewport.width);
    expect(dimensions.content).toBeLessThanOrEqual(viewport.width);
    const folder = path.resolve("..", ".cache", "account-passwords");
    await mkdir(folder, { recursive: true });
    await page.screenshot({
      path: path.join(folder, `change-password-${viewport.width}.png`),
      fullPage: true,
    });

    await passwordSection
      .getByLabel("Current password", { exact: true })
      .fill(initialPassword);
    await passwordSection.getByLabel("New password", { exact: true }).fill(nextPassword);
    await passwordSection
      .getByLabel("Confirm new password", { exact: true })
      .fill(nextPassword);
    await passwordSection
      .getByRole("button", { name: "Change password", exact: true })
      .click();
    await expect(
      page.getByRole("link", { name: "Go to login", exact: true }),
    ).toBeVisible();
    await expect(page).toHaveURL(/\/account$/);
    await expect(passwordSection.getByLabel("New password", { exact: true })).toHaveCount(
      0,
    );
    expect(
      (
        await page.request.get(apiPath("/api/v1/auth/me"), { headers: oldAuthorization })
      ).status(),
    ).toBe(401);
    expect((await page.request.post(apiPath("/api/v1/auth/refresh"))).status()).toBe(401);

    await page.getByRole("link", { name: "Go to login", exact: true }).click();
    await expect(page).toHaveURL(/\/login$/);
    const oldLogin = await page.request.post(apiPath("/api/v1/auth/login"), {
      data: { email, password: initialPassword },
    });
    expect(oldLogin.status()).toBe(401);
    const newLogin = await page.request.post(apiPath("/api/v1/auth/login"), {
      data: { email, password: nextPassword },
    });
    expect(newLogin.status()).toBe(200);
    const newAccount = await newLogin.json();
    expect(newAccount.user.id).toBe(account.user.id);
    const savedArticle = await page.request.get(
      apiPath(`/api/v1/articles/${article.id}`),
      {
        headers: { Authorization: `Bearer ${newAccount.access_token}` },
      },
    );
    expect(savedArticle.status()).toBe(200);
    expect((await savedArticle.json()).content).toEqual(article.content);
  });
}
