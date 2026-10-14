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

for (const viewport of [
  { width: 1440, height: 900 },
  { width: 390, height: 844 },
]) {
  test(`AI limit keeps the topic and saved article usable at ${viewport.width}px`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const original = await createDraft(page, `quota-${viewport.width}`);
    await page.goto("/dashboard");
    await selectArticle(page, original.query);
    await closeMobileNavigation(page);
    const article = page.getByRole("tabpanel", { name: "Article", exact: true });
    await expect(article).toBeVisible();
    const before = await article.innerText();
    let requests = 0;
    let release!: () => void;
    const pending = new Promise<void>((resolve) => {
      release = resolve;
    });
    await page.route("**/api/v1/articles", async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      requests++;
      await pending;
      await route.fulfill({
        status: 503,
        json: {
          error: {
            code: "AI_DAILY_LIMIT_REACHED",
            message:
              "The AI service has reached its daily limit. Please try again later. Your topic and saved articles are unchanged.",
            request_id: "quota-fixture",
            details: {
              retry_after_seconds: 3600,
              retry_at: new Date(Date.now() + 3600000).toISOString(),
            },
          },
        },
      });
    });
    const topic = page.getByRole("textbox", { name: "Topic / search query" });
    await topic.fill("An article topic to keep");
    await page.getByRole("button", { name: "Generate", exact: true }).click();
    await expect(
      page.getByText("Wait for the current action to finish before exporting."),
    ).toBeVisible();
    release();
    const alert = page.getByRole("alert").filter({ hasText: /daily limit/ });
    await expect(alert).toContainText("Suggested retry:");
    await expect(topic).toHaveValue("An article topic to keep");
    await expect(
      page.getByRole("button", { name: "Generate", exact: true }),
    ).toBeEnabled();
    await expect(
      page.getByRole("button", { name: "Download Markdown", exact: true }),
    ).toBeEnabled();
    expect(await article.innerText()).toBe(before);
    expect(requests).toBe(1);
    expect(errors).toEqual([]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await mkdir(screenshots, { recursive: true });
    await page.screenshot({
      path: path.join(screenshots, `quota-recovery-${viewport.width}.png`),
      fullPage: true,
    });
  });
}

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
  await expect(page.getByRole("heading", { name: "Article workspace" })).toBeVisible();
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
  test(`clarification preserves the current draft and accepts a refined topic at ${viewport.width}px`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    const original = await createDraft(page, `clarification-${viewport.width}`);
    await page.goto("/dashboard");
    await selectArticle(page, original.query);
    const originalHeading = page.getByRole("heading", {
      name: original.title,
      exact: true,
    });
    await expect(originalHeading).toBeVisible();
    let clarify = true;
    await page.route("**/api/v1/articles", async (route) => {
      if (route.request().method() === "POST" && clarify) {
        clarify = false;
        await route.fulfill({
          status: 400,
          json: {
            error: {
              code: "TOPIC_CLARIFICATION_REQUIRED",
              message: "Which location do you mean by ABC Trek?",
              request_id: "local-clarification",
            },
          },
        });
      } else await route.fallback();
    });
    const topic = page.getByRole("textbox", { name: "Topic / search query" });
    await topic.fill("ABC Trek");
    await page.getByRole("button", { name: "Generate", exact: true }).click();
    await expect(page.getByText("Which location do you mean by ABC Trek?")).toBeVisible();
    await expect(topic).toHaveValue("ABC Trek");
    await expect(topic).toBeFocused();
    await expect(originalHeading).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBe(true);
    await mkdir(screenshots, { recursive: true });
    await page.screenshot({
      path: path.join(screenshots, `clarification-${viewport.width}.png`),
    });
    await topic.fill("Annapurna Base Camp Trek in Nepal");
    await page.getByRole("button", { name: "Generate", exact: true }).click();
    await expect(
      page.getByRole("heading", {
        name: "A Practical Guide to Annapurna Base Camp Trek in Nepal",
        exact: true,
      }),
    ).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("One detail before we write")).toBeHidden();
  });

  test(`protect unsaved drafts and export saved versions at ${viewport.width}px`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    const original = await createDraft(page, String(viewport.width));
    expect(original.seo?.review_status).toBe("generated");
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
    expect(
      await page
        .getByRole("tabpanel", { name: "Article", exact: true })
        .evaluate((element) => element.getBoundingClientRect().height),
    ).toBeGreaterThan(280);
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
    await expect(page.getByText("Needs review", { exact: true })).toBeVisible();
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

    // A deliberate SEO edit is persisted separately from AI-generated quality.
    await page.getByRole("button", { name: "Edit SEO", exact: true }).click();
    const editedSeoTitle = "Balcony herbs: soil, light and watering";
    await page.getByLabel(/SEO Title/i).fill(editedSeoTitle);
    await page.getByRole("button", { name: "Save version", exact: true }).click();
    await expect(page.getByText("Edited by you", { exact: true })).toBeVisible();
    await page.reload();
    await selectArticle(page, original.query);
    await page.getByRole("tab", { name: "SEO Metadata", exact: true }).click();
    await expect(page.getByText("Edited by you", { exact: true })).toBeVisible();
    await expect(page.getByText(editedSeoTitle, { exact: true })).toBeVisible();
    await page.screenshot({
      path: path.join(screenshots, `seo-review-status-${viewport.width}.png`),
      fullPage: true,
    });

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
        .filter({ hasText: "Version 4" })
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

    await page.getByRole("tab", { name: "SEO Metadata", exact: true }).click();
    await expect(
      page.getByText("AI draft — review before publishing", { exact: true }),
    ).toBeVisible();

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
  // The primary article is visible before opening the supporting evidence.
  const articlePanel = page.getByRole("tabpanel", { name: "Article", exact: true });
  await expect(articlePanel).toBeVisible();
  expect(
    await articlePanel.evaluate((element) => element.getBoundingClientRect().top),
  ).toBeLessThan(450);
  await expect(page.getByRole("region", { name: "Article sources" })).toHaveCount(0);
  await page.getByRole("tab", { name: "Sources", exact: true }).click();
  await expect(
    page.getByRole("status").filter({ hasText: /Sources retrieved/ }),
  ).toBeVisible();
  const sources = page.getByRole("region", { name: "Article sources" });
  const sourceLink = sources.getByRole("link", { name: "Growing herbs" });
  await expect(sourceLink).toBeVisible();
  await sources.getByText("View 1 source", { exact: true }).press("Enter");
  await expect(sourceLink).toBeHidden();
  await sources.getByText("View 1 source", { exact: true }).press("Enter");
  await expect(sourceLink).toBeVisible();
  expect(
    await page
      .getByRole("tabpanel", { name: "Sources", exact: true })
      .evaluate((element) => element.getBoundingClientRect().height),
  ).toBeGreaterThan(280);
  await expect(
    page
      .getByRole("region", { name: "Article sources" })
      .getByRole("link", { name: "Growing herbs" }),
  ).toHaveAttribute("href", sourceUrl);
  expect(await markdownDownload(page)).toBe(persisted.markdown);
});
