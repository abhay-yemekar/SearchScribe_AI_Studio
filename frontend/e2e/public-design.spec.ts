import { expect, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";

test("public website works on mobile with reduced motion and keyboard controls", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Start with");
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBe(true);
  await page.getByRole("button", { name: "Open navigation", exact: true }).click();
  await expect(page.getByRole("navigation", { name: "Mobile navigation" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Open navigation", exact: true }),
  ).toBeFocused();
  await page.getByRole("tab", { name: "Professional", exact: true }).focus();
  await page.keyboard.press("End");
  await expect(page.getByRole("tab", { name: "Minimal", exact: true })).toBeFocused();
  await expect(page.getByRole("tabpanel")).toContainText("Quiet water.");
  await page.getByRole("button", { name: "Use dark theme" }).click();
  await expect(page.locator(".marketing-shell")).toHaveAttribute("data-theme", "dark");
  const motion = await page
    .locator(".typed-topic")
    .evaluate((el) => getComputedStyle(el).animationName);
  expect(motion).toBe("none");
  for (const route of ["/features", "/how-it-works", "/example", "/privacy", "/login"]) {
    await page.goto(route);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBe(true);
  }
});

test("desktop walkthrough is operable and makes no generation requests", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  let generationRequests = 0;
  page.on("request", (request) => {
    if (request.method() === "POST" && /articles\/(generate|rewrite)/.test(request.url()))
      generationRequests++;
  });
  await page.goto("/");
  await page.getByRole("button", { name: /04 SEO/ }).click();
  await expect(page.locator(".story-seo")).toContainText("A first look at Kerala");
  await page.getByRole("button", { name: /06 Export/ }).click();
  await expect(page.locator(".story-export")).toContainText("kerala-first-draft.html");
  await page.getByRole("tab", { name: "Casual", exact: true }).click();
  await expect(page.getByRole("tabpanel")).toContainText("slowing down");
  expect(generationRequests).toBe(0);

  if (process.env.SCREENSHOT_DIR) {
    const folder = path.resolve(process.env.SCREENSHOT_DIR);
    await mkdir(folder, { recursive: true });
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({
      path: path.join(folder, "redesign-home.png"),
      fullPage: true,
    });
    await page.getByRole("button", { name: "Use dark theme" }).click();
    await page.screenshot({
      path: path.join(folder, "redesign-dark.png"),
      fullPage: true,
    });
    await page.getByRole("button", { name: "Use light theme" }).click();
    for (const [index, name] of [
      "01 Topic",
      "02 Structure",
      "03 Draft",
      "04 SEO",
      "05 Versions",
      "06 Export",
    ].entries()) {
      await page.getByRole("button", { name, exact: true }).click();
      await page
        .locator(".story-board")
        .screenshot({ path: path.join(folder, `journey-${index}.png`) });
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({
      path: path.join(folder, "redesign-mobile.png"),
      fullPage: true,
    });
  }
});

test("desktop scroll does not discard a manually selected writing step", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("/");
  await page
    .locator(".story-section")
    .evaluate((el) => el.scrollIntoView({ block: "start" }));
  const seo = page.getByRole("button", { name: /04 SEO/ });
  await seo.click();
  await expect(seo).toHaveAttribute("aria-pressed", "true");
  const before = await page.evaluate(() => scrollY);
  await page.mouse.wheel(0, 24);
  await expect.poll(() => page.evaluate(() => scrollY)).toBeGreaterThan(before);
  await expect(seo).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".story-seo")).toContainText("A first look at Kerala");
});
