import { expect, test, type Page } from "@playwright/test";
import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";

import type { ArticleDetail } from "../lib/api/schemas";

// These accounts and drafts belong only to the disposable mock-provider stack.
const apiOrigin = process.env.E2E_API_URL ?? "";
if (apiOrigin && !/^http:\/\/127\.0\.0\.1:\d+$/.test(apiOrigin)) {
  throw new Error("E2E_API_URL must be an isolated loopback API.");
}
const apiPath = (pathname: string) => `${apiOrigin}${pathname}`;
const screenshots = path.resolve("..", ".cache", "writing-workflow");

test.beforeEach(async ({ page }) => {
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

async function createDraft(page: Page, suffix: string): Promise<ArticleDetail> {
  const signup = await page.request.post(apiPath("/api/v1/auth/signup"), {
    data: {
      name: "Writing Test",
      email: `writing-${Date.now()}-${suffix}@test.dev`,
      password: "local-writing-password-1",
    },
  });
  expect(signup.status()).toBe(201);
  const account = await signup.json();
  const generated = await page.request.post(apiPath("/api/v1/articles"), {
    headers: { Authorization: `Bearer ${account.access_token}` },
    data: { query: "Growing herbs on a balcony" },
  });
  expect(generated.status()).toBe(201);
  return generated.json();
}

async function selectArticle(page: Page, query: string) {
  const opener = page.getByRole("button", { name: "Open article navigation" });
  if (await opener.isVisible()) await opener.click();
  await page
    .getByRole("complementary", { name: "Article navigation" })
    .or(page.getByRole("dialog", { name: "Article navigation" }))
    .getByRole("button", { name: new RegExp(`^(?!Delete ).*${query}`, "i") })
    .click();
}

async function closeMobileNavigation(page: Page) {
  const sidebar = page.getByRole("dialog", { name: "Article navigation" });
  if (await sidebar.isVisible()) {
    await sidebar.getByRole("button", { name: "Close article navigation" }).click();
  }
}

async function keepEditing(page: Page, draft: string) {
  const dialog = page.getByRole("dialog", { name: "Discard unsaved changes?" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Keep editing", exact: true }).click();
  await closeMobileNavigation(page);
  await expect(
    page.getByRole("textbox", { name: "Introduction", exact: true }),
  ).toHaveValue(draft);
  await expect(
    page.getByRole("status").filter({ hasText: /^Unsaved changes$/ }),
  ).toBeVisible();
}

async function markdownDownload(page: Page): Promise<string> {
  const pending = page.waitForEvent("download");
  await page
    .getByRole("group", { name: "Export article" })
    .getByRole("button", { name: "Download Markdown", exact: true })
    .click();
  const download = await pending;
  expect(download.suggestedFilename()).toMatch(/\.md$/);
  const filename = await download.path();
  expect(filename).not.toBeNull();
  return readFile(filename!, "utf8");
}

async function beforeUnloadIsPrevented(page: Page) {
  return page.evaluate(() => {
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    return event.defaultPrevented;
  });
}

for (const viewport of [
  { width: 1422, height: 900 },
  { width: 390, height: 844 },
]) {
  test(`protect unsaved drafts and export saved versions at ${viewport.width}px`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    const original = await createDraft(page, String(viewport.width));
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Article workspace" })).toBeVisible();

    // A second real mock-provider generation makes article switching observable.
    await page.getByLabel("Topic / search query").fill("Planning a reading routine");
    await page.getByRole("button", { name: "Generate", exact: true }).click();
    await expect(
      page.getByRole("heading", {
        name: /practical guide to planning a reading routine/i,
      }),
    ).toBeVisible({
      timeout: 30_000,
    });
    await selectArticle(page, original.query);
    await page.getByRole("button", { name: "Edit article", exact: true }).click();

    const changedIntroduction =
      "A saved editorial introduction with deliberate details and a clear point of view.";
    await page
      .getByRole("textbox", { name: "Introduction", exact: true })
      .fill(changedIntroduction);
    const exports = page.getByRole("group", { name: "Export article" });
    await expect(
      exports.getByRole("button", { name: "Download HTML", exact: true }),
    ).toBeDisabled();
    await expect(
      exports.getByRole("button", { name: "Download Markdown", exact: true }),
    ).toBeDisabled();
    expect(await beforeUnloadIsPrevented(page)).toBe(true);

    await page.getByRole("tab", { name: "SEO Metadata", exact: true }).click();
    await keepEditing(page, changedIntroduction);
    await expect(page.getByRole("tab", { name: "Article", exact: true })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    await page.getByRole("link", { name: "Website", exact: true }).click();
    await keepEditing(page, changedIntroduction);
    await expect(page).toHaveURL(/\/dashboard$/);

    await page.getByRole("button", { name: "Cancel", exact: true }).click();
    await keepEditing(page, changedIntroduction);
    await selectArticle(page, "Planning a reading routine");
    await keepEditing(page, changedIntroduction);

    await mkdir(screenshots, { recursive: true });
    await page.screenshot({
      path: path.join(screenshots, `unsaved-draft-${viewport.width}.png`),
      fullPage: true,
    });
    const dimensions = await page.evaluate(() => ({
      viewport: window.innerWidth,
      content: document.documentElement.scrollWidth,
    }));
    expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport);

    // A failed optimistic save must not discard the user's text or export old data.
    let failNextSave = true;
    await page.route(`**/api/v1/articles/${original.id}/content`, async (route) => {
      if (route.request().method() === "PUT" && failNextSave) {
        failNextSave = false;
        await route.fulfill({
          status: 409,
          contentType: "application/json",
          body: JSON.stringify({
            error: {
              code: "VERSION_CONFLICT",
              message: "The article changed in another session.",
              request_id: "local-writing-conflict",
            },
          }),
        });
        return;
      }
      await route.fallback();
    });
    await page.getByRole("button", { name: "Save version", exact: true }).click();
    await expect(
      page
        .getByRole("alert")
        .filter({ hasText: "The article changed in another session." }),
    ).toHaveText("The article changed in another session.");
    await expect(
      page.getByRole("textbox", { name: "Introduction", exact: true }),
    ).toHaveValue(changedIntroduction);
    await expect(
      exports.getByRole("button", { name: "Download Markdown", exact: true }),
    ).toBeDisabled();
    await page.getByRole("button", { name: "Save version", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Edit article", exact: true }),
    ).toBeVisible();
    expect(await beforeUnloadIsPrevented(page)).toBe(false);
    const savedMarkdown = await markdownDownload(page);
    expect(savedMarkdown).toContain(changedIntroduction);
    expect(savedMarkdown).toContain("Unresearched draft");

    // Opening an editor alone is not dirty; switching tabs needs no confirmation.
    await page.getByRole("button", { name: "Edit article", exact: true }).click();
    await page.getByRole("tab", { name: "SEO Metadata", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Edit SEO", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("dialog", { name: "Discard unsaved changes?" }),
    ).toHaveCount(0);

    // SEO uses the same protections and discarding reveals the saved metadata.
    await page.getByRole("button", { name: "Edit SEO", exact: true }).click();
    await page.getByLabel(/SEO Title/i).fill("A temporary SEO title");
    await page.getByRole("tab", { name: "Article", exact: true }).click();
    const discard = page.getByRole("dialog", { name: "Discard unsaved changes?" });
    await expect(discard).toBeVisible();
    await discard.getByRole("button", { name: "Discard changes", exact: true }).click();
    await expect(page.getByText(changedIntroduction, { exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "SEO Metadata", exact: true }).click();
    await expect(page.getByText("A temporary SEO title", { exact: true })).toHaveCount(0);

    // Restored snapshots, rather than stale editor text, are exported.
    await page.getByRole("tab", { name: "Versions", exact: true }).click();
    await page
      .getByRole("listitem")
      .filter({ hasText: "Version 1" })
      .getByRole("button", { name: /restore/i })
      .click();
    await expect(
      page
        .getByRole("tabpanel", { name: "Versions", exact: true })
        .getByRole("listitem")
        .filter({ hasText: "Version 3" })
        .getByText("Current", { exact: true }),
    ).toBeVisible();
    await page.getByRole("tab", { name: "Article", exact: true }).click();
    await expect(
      page.getByText(original.content.introduction, { exact: true }),
    ).toBeVisible();
    const restoredMarkdown = await markdownDownload(page);
    expect(restoredMarkdown).toContain(original.content.introduction);
    expect(restoredMarkdown).not.toContain(changedIntroduction);
    expect(restoredMarkdown).toContain("Unresearched draft");

    await page.getByRole("tab", { name: "Article", exact: true }).click();
    await page.getByRole("button", { name: "Edit article", exact: true }).click();
    await page
      .getByRole("textbox", { name: "Introduction", exact: true })
      .fill("Discard this temporary paragraph.");
    await page.getByRole("link", { name: "Website", exact: true }).click();
    await page
      .getByRole("dialog", { name: "Discard unsaved changes?" })
      .getByRole("button", { name: "Discard changes", exact: true })
      .click();
    await expect(page).toHaveURL(/\/$/);
    await expect(
      page.getByRole("heading", { name: /start with a thought/i }),
    ).toBeVisible();
  });
}

test("browser Back and Forward retain the active in-memory draft", async ({ page }) => {
  const original = await createDraft(page, "history");
  await page.goto("/");
  await page.getByRole("link", { name: "Open workspace", exact: true }).first().click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await selectArticle(page, original.query);
  await page.getByRole("button", { name: "Edit article", exact: true }).click();
  const introduction =
    "An unfinished draft kept safely during browser history navigation.";
  await page
    .getByRole("textbox", { name: "Introduction", exact: true })
    .fill(introduction);
  await expect(
    page.getByRole("status").filter({ hasText: /^Unsaved changes$/ }),
  ).toBeVisible();
  await page.goBack();
  await expect(
    page.getByRole("heading", { name: /start with a thought/i }),
  ).toBeVisible();
  await page.goForward();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(
    page.getByRole("textbox", { name: "Introduction", exact: true }),
  ).toHaveValue(introduction);
  await expect(
    page.getByRole("status").filter({ hasText: /^Unsaved changes$/ }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("group", { name: "Export article" })
      .getByRole("button", { name: "Download Markdown", exact: true }),
  ).toBeDisabled();
});

test("Markdown download preserves the persisted source citations", async ({ page }) => {
  const original = await createDraft(page, "sources");
  const sourceUrl = "https://www.rhs.org.uk/herbs/growing";
  // Model a researched API snapshot without making an external retrieval or
  // changing provenance through the editor's real save endpoint.
  const persisted = {
    ...original,
    content: {
      ...original.content,
      research: {
        status: "sources_retrieved",
        retrieved_at: "2026-10-13T00:00:00Z",
        sources: [
          {
            id: "source-1",
            title: "Growing herbs",
            url: sourceUrl,
            published_at: "2026-10-12",
          },
        ],
      },
    },
    markdown: `# ${original.title}\n\n${original.content.introduction}\n\n## Sources\n\n[Growing herbs](${sourceUrl})\n\nSources retrieved: 2026-10-13T00:00:00Z. Reported publication/update: 2026-10-12 (estimated). Review claims before publishing.\n`,
  };
  await page.route(`**/api/v1/articles/${original.id}`, async (route) => {
    if (route.request().method() !== "GET") {
      await route.fallback();
      return;
    }
    await route.fulfill({ json: persisted });
  });
  await page.goto("/dashboard");
  await selectArticle(page, original.query);
  await expect(
    page.getByRole("status").filter({ hasText: /Sources retrieved/ }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("region", { name: "Article sources" })
      .getByRole("link", { name: "Growing herbs" }),
  ).toHaveAttribute("href", sourceUrl);
  expect(await markdownDownload(page)).toBe(persisted.markdown);
});
