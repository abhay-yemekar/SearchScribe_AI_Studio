import { expect, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";

const api = process.env.E2E_API_URL ?? "";
if (api && !/^http:\/\/127\.0\.0\.1:\d+$/.test(api))
  throw new Error("Use an isolated loopback API.");
const capture = process.env.CAPTURE_PRODUCT_MEDIA === "1";
const media = path.resolve(__dirname, "../../screenshots");
test.use({ deviceScaleFactor: 2 });

test.beforeEach(async ({ page }) => {
  if (api)
    await page.route("**/api/v1/**", async (route) => {
      const url = new URL(route.request().url());
      await route.fulfill({
        response: await route.fetch({ url: `${api}${url.pathname}${url.search}` }),
      });
    });
});

test("one refresh restores the profile and public navigation reuses it", async ({
  page,
}) => {
  const email = `product-${Date.now()}@test.dev`;
  const signup = await page.request.post(`${api}/api/v1/auth/signup`, {
    data: {
      name: "Demo Writer",
      email,
      password: "local-product-demo-1",
    },
  });
  expect(signup.status()).toBe(201);
  const requests: string[] = [];
  page.on("request", (request) => {
    if (/\/auth\/(me|refresh)$/.test(new URL(request.url()).pathname))
      requests.push(new URL(request.url()).pathname);
  });
  let releaseRefresh!: () => void;
  const waiting = new Promise<void>((resolve) => {
    releaseRefresh = resolve;
  });
  await page.route("**/api/v1/auth/refresh", async (route) => {
    await waiting;
    await route.fallback();
  });
  await page.goto("/dashboard");
  try {
    await expect(
      page.getByRole("heading", { name: "Opening your workspace", exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Website", exact: true })).toBeVisible();
  } finally {
    releaseRefresh();
  }
  await expect(
    page.getByRole("heading", { name: "Article workspace", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Website", exact: true }).click();
  await page.getByRole("link", { name: "Features", exact: true }).first().click();
  await page.getByRole("link", { name: "Open workspace", exact: true }).first().click();
  await expect(
    page.getByRole("heading", { name: "Article workspace", exact: true }),
  ).toBeVisible();
  expect(requests.filter((value) => value.endsWith("/refresh"))).toHaveLength(1);
  expect(requests.filter((value) => value.endsWith("/me"))).toHaveLength(0);
});

test("editorial artwork loads and reduced motion keeps it still", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const artwork = page.getByRole("img", { name: /Sculptural paper folds/ });
  await artwork.scrollIntoViewIfNeeded();
  await expect(artwork).toBeVisible();
  await expect
    .poll(() =>
      artwork.evaluate(
        (image: HTMLImageElement) => image.complete && image.naturalWidth > 0,
      ),
    )
    .toBe(true);
  expect(
    await artwork.evaluate((element) => getComputedStyle(element).animationName),
  ).toBe("none");
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBe(true);
});

test("capture current product media with a synthetic mock account", async ({ page }) => {
  test.skip(!capture, "Media capture is opt-in; no binary files are produced in CI.");
  await mkdir(media, { recursive: true });
  await mkdir(path.join(media, ".workflow-frames"), { recursive: true });
  await page.emulateMedia({ reducedMotion: "reduce" });
  // 1920x1080 CSS pixels at 2x produces an actual 3840x2160 PNG.
  const screenshotStyle = "nextjs-portal { display: none !important; }";
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto("/");
  await page.evaluate(() => document.fonts.ready);
  expect(await page.evaluate(() => ({ width: innerWidth, height: innerHeight }))).toEqual(
    { width: 1920, height: 1080 },
  );
  await page.screenshot({ path: path.join(media, "studio-home-4k.png"), style: screenshotStyle });
  await page
    .getByRole("img", { name: /Sculptural paper folds/ })
    .scrollIntoViewIfNeeded();
  await expect
    .poll(() =>
      page
        .getByRole("img", { name: /Sculptural paper folds/ })
        .evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth > 0),
    )
    .toBe(true);
  await page
    .locator(".editorial-section")
    .evaluate((element) => element.scrollIntoView({ block: "start" }));
  await page.screenshot({ path: path.join(media, "studio-editorial-4k.png"), style: screenshotStyle });
  const account = await page.request.post(`${api}/api/v1/auth/signup`, {
    data: {
      name: "Demo Writer",
      email: `media-${Date.now()}@test.dev`,
      password: "local-product-demo-1",
    },
  });
  expect(account.status()).toBe(201);
  const { access_token } = await account.json();
  const generated = await page.request.post(`${api}/api/v1/articles`, {
    headers: { Authorization: `Bearer ${access_token}` },
    data: { query: "Planning a reading routine" },
  });
  expect(generated.status()).toBe(201);
  await page.goto("/dashboard");
  await page
    .getByRole("button", { name: /^A Practical Guide to Planning a reading routine v1/ })
    .click();
  await expect(
    page.getByRole("tabpanel", { name: "Article", exact: true }),
  ).toBeVisible();
  await page.screenshot({ path: path.join(media, "studio-workspace-4k.png"), style: screenshotStyle });
  await page.setViewportSize({ width: 1440, height: 900 });
  const tabs = [
    "Article",
    "SEO Metadata",
    "HTML Preview",
    "Sources",
    "Versions",
    "Article",
  ];
  for (const [index, name] of tabs.entries()) {
    await page.getByRole("tab", { name, exact: true }).click();
    await expect(page.getByRole("tabpanel", { name, exact: true })).toBeVisible();
    if (name === "HTML Preview")
      await expect(page.getByTitle(/^HTML preview of /)).toBeVisible();
    await page.screenshot({ path: path.join(media, ".workflow-frames", `${index}.png`), style: screenshotStyle });
  }
});
