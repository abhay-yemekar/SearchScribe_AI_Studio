import { expect, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";

for (const viewport of [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
]) {
  test(`signup layout keeps navigation and branding separate at ${viewport.width}px`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    await page.route("**/api/v1/auth/google/challenge", (route) =>
      route.fulfill({ json: { enabled: false } }),
    );
    await page.goto("/login?mode=signup");
    await expect(page.getByRole("heading", { name: "Create account" })).toBeVisible();
    await expect(
      page.getByText("Google sign-in is unavailable on this instance.", { exact: false }),
    ).toBeVisible();

    const back = page.getByRole("link", { name: "Back to SearchScribe" });
    const logo = page.locator("header .brand-logo");
    const backBox = await back.boundingBox();
    const logoBox = await logo.boundingBox();
    expect(backBox).not.toBeNull();
    expect(logoBox).not.toBeNull();
    if (backBox && logoBox) {
      const separate =
        backBox.x + backBox.width <= logoBox.x ||
        logoBox.x + logoBox.width <= backBox.x ||
        backBox.y + backBox.height <= logoBox.y ||
        logoBox.y + logoBox.height <= backBox.y;
      expect(separate).toBe(true);
    }
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBe(true);
    await page.getByLabel("Name", { exact: true }).fill("Layout preview");
    await expect(
      page.getByRole("button", { name: "Sign up", exact: true }),
    ).toBeVisible();
    await back.focus();
    await expect(back).toBeFocused();
    if (process.env.SCREENSHOT_DIR) {
      const folder = path.resolve(process.env.SCREENSHOT_DIR);
      await mkdir(folder, { recursive: true });
      await page.evaluate(() => document.fonts.ready);
      await page.screenshot({
        path: path.join(folder, `signup-${viewport.width}.png`),
        fullPage: true,
      });
    }
  });
}
