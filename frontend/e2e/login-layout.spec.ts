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

test("login fits a short desktop and validation remains reachable by scrolling", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1422, height: 588 });
  await page.route("**/api/v1/auth/google/challenge", (route) =>
    route.fulfill({
      json: { enabled: true, client_id: "layout-client", nonce: "layout-nonce" },
    }),
  );
  // Exercise Google's normal 40px button footprint without external sign-in or identity sharing.
  await page.route("https://accounts.google.com/gsi/client", (route) =>
    route.fulfill({
      contentType: "application/javascript",
      body: `window.google = { accounts: { id: {
        initialize() {},
        renderButton(container) {
          const button = document.createElement('button');
          button.type = 'button';
          button.textContent = 'Sign in with Google';
          button.style.cssText = 'height:40px;width:280px';
          container.append(button);
        }
      } } };`,
    }),
  );
  await page.goto("/login");
  await expect(page.getByRole("button", { name: "Sign in with Google" })).toBeVisible();
  expect(await page.evaluate(() => ({ width: innerWidth, height: innerHeight }))).toEqual(
    {
      width: 1422,
      height: 588,
    },
  );
  expect(
    await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight),
  ).toBe(true);
  const submit = page.getByRole("button", { name: "Login", exact: true });
  const switchMode = page.getByRole("button", { name: "Don't have an account? Sign up" });
  for (const control of [submit, switchMode]) {
    const box = await control.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.y + box!.height).toBeLessThanOrEqual(588);
  }
  if (process.env.SCREENSHOT_DIR) {
    const folder = path.resolve(process.env.SCREENSHOT_DIR);
    await mkdir(folder, { recursive: true });
    await page.screenshot({ path: path.join(folder, "login-short-desktop.png") });
  }
  await switchMode.click();
  await expect(page.getByRole("heading", { name: "Create account" })).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight),
  ).toBe(true);
  if (process.env.SCREENSHOT_DIR) {
    const folder = path.resolve(process.env.SCREENSHOT_DIR);
    await page.screenshot({ path: path.join(folder, "signup-short-desktop.png") });
  }
  await page.getByRole("button", { name: "Sign up", exact: true }).click();
  await expect(page.getByText("Name is required", { exact: true })).toBeVisible();
  await expect(page.getByText("Enter a valid email", { exact: true })).toBeVisible();
  // A zoomed or shorter window may need vertical scrolling; no panel is height-locked.
  await page.setViewportSize({ width: 1422, height: 360 });
  const signup = page.getByRole("button", { name: "Sign up", exact: true });
  await signup.scrollIntoViewIfNeeded();
  await signup.focus();
  await expect(signup).toBeFocused();
  const box = await signup.boundingBox();
  expect(box!.y + box!.height).toBeLessThanOrEqual(360);
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBe(true);
});
