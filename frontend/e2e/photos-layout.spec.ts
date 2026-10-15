import { expect, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";

const captures = path.resolve(__dirname, "../../.cache/photos");
const apiOrigin = process.env.E2E_API_URL ?? "";
if (apiOrigin && !/^http:\/\/127\.0\.0\.1:\d+$/.test(apiOrigin)) {
  throw new Error("Photo layout tests require the isolated loopback API.");
}

for (const viewport of [
  { width: 1440, height: 900 },
  { width: 390, height: 844 },
]) {
  test(`saved photo layout and discard protection at ${viewport.width}px`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    if (apiOrigin)
      await page.route("**/api/v1/**", async (route) => {
        const url = new URL(route.request().url());
        await route.fulfill({
          response: await route.fetch({
            url: `${apiOrigin}${url.pathname}${url.search}`,
          }),
        });
      });
    const signup = await page.request.post(`${apiOrigin}/api/v1/auth/signup`, {
      data: {
        name: "Photo Layout Test",
        email: `photo-layout-${Date.now()}-${viewport.width}@example.com`,
        password: "local-photo-password-1",
      },
    });
    expect(signup.status()).toBe(201);
    const account = await signup.json();
    const generated = await page.request.post(`${apiOrigin}/api/v1/articles`, {
      headers: { Authorization: `Bearer ${account.access_token}` },
      data: { query: "A balcony herb garden" },
    });
    expect(generated.status()).toBe(201);
    const original = await generated.json();
    // An explicit UI-only fixture: no real photo search or fabricated backend
    // attribution. API ownership/signatures/snapshots are tested in test_photos.py.
    const photo = {
      provider: "commons",
      source_id: 123,
      id: "a".repeat(32),
      section_id: null,
      title: "Photo layout fixture",
      creator: "Test creator",
      license_name: "CC BY 4.0",
      license_url: "https://creativecommons.org/licenses/by/4.0/",
      width: 4032,
      height: 2688,
      source_url: "https://commons.wikimedia.org/wiki/File:Fixture.jpg",
      original_url: "https://upload.wikimedia.org/wikipedia/commons/a/ab/Fixture.jpg",
      preview_url: "https://upload.wikimedia.org/wikipedia/commons/a/ab/Fixture.jpg",
      alt: "Photo layout test fixture",
    };
    await page.route(photo.preview_url, (route) =>
      route.fulfill({
        contentType: "image/svg+xml",
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800"><rect width="1200" height="800" fill="#c8ddd6"/><text x="80" y="400" font-size="48">Photo layout fixture</text></svg>',
      }),
    );
    await page.route(`**/api/v1/articles/${original.id}`, async (route) => {
      if (route.request().method() !== "GET") return route.fallback();
      await route.fulfill({
        json: { ...original, content: { ...original.content, photos: [photo] } },
      });
    });
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Article workspace" })).toBeVisible();
    const navigation = page.getByRole("button", { name: "Open article navigation" });
    if (await navigation.isVisible()) await navigation.click();
    await page
      .getByRole("button", { name: /^A Practical Guide to A balcony herb garden/ })
      .click();
    const photoImage = page.getByRole("img", { name: photo.alt, exact: true });
    await expect(photoImage).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Test creator", exact: true }),
    ).toHaveAttribute("href", photo.source_url);
    expect(await page.evaluate(() => innerWidth)).toBe(viewport.width);
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBe(true);
    await mkdir(captures, { recursive: true });
    await page.screenshot({
      path: path.join(captures, `article-layout-${viewport.width}.png`),
      fullPage: true,
    });
    await page.getByRole("tab", { name: "Photos", exact: true }).click();
    await page.getByRole("button", { name: "Edit photos", exact: true }).click();
    await page
      .getByRole("textbox", { name: /Alt text/ })
      .fill("An unsaved accessible description");
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBe(true);
    await page.screenshot({
      path: path.join(captures, `photo-controls-${viewport.width}.png`),
      fullPage: true,
    });
    await page.getByRole("tab", { name: "Article", exact: true }).click();
    const discard = page.getByRole("dialog", { name: "Discard unsaved changes?" });
    await expect(discard).toBeVisible();
    await expect(
      discard.getByRole("button", { name: "Keep editing", exact: true }),
    ).toBeFocused();
    await discard.getByRole("button", { name: "Keep editing", exact: true }).click();
    await expect(page.getByRole("textbox", { name: /Alt text/ })).toHaveValue(
      "An unsaved accessible description",
    );
    expect(errors).toEqual([]);
  });
}
