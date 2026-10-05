import { expect, test } from "@playwright/test";

test("article navigation works on a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: /sign up/i }).click();
  await page.getByLabel("Name").fill("Mobile Tester");
  await page.getByLabel("Email").fill(`mobile-${Date.now()}@test.dev`);
  await page.getByLabel("Password").fill("e2e-password-1");
  await page.getByRole("button", { name: /^Sign up$/ }).click();

  const menu = page.getByRole("button", { name: "Open article navigation" });
  const sidebar = page.locator("#article-sidebar");
  await expect(menu).toBeVisible({ timeout: 15_000 });
  await expect(sidebar).toBeHidden();

  await menu.click();
  await expect(page.getByRole("dialog", { name: "Article navigation" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Close article navigation" }).last(),
  ).toBeFocused();

  await page.keyboard.press("Escape");
  await expect(sidebar).toBeHidden();
  await expect(menu).toBeFocused();

  await menu.click();
  await page.getByRole("button", { name: "New article" }).click();
  await expect(sidebar).toBeHidden();
  await expect(page.getByLabel("Topic / search query")).toBeFocused();
});
