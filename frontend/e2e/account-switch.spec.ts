import { expect, test } from "@playwright/test";

// Accounts and articles here belong only to the disposable mock-provider stack.
test("after a session expires, the next person on the tab never sees the last one's articles", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const signup = await page.request.post("/api/v1/auth/signup", {
    data: {
      name: "First Person",
      email: `first-${Date.now()}@test.dev`,
      password: "local-switch-password-1",
    },
  });
  expect(signup.status()).toBe(201);
  const generated = await page.request.post("/api/v1/articles", {
    headers: { Authorization: `Bearer ${(await signup.json()).access_token}` },
    data: { query: "Private allotment notes" },
  });
  expect(generated.status()).toBe(201);

  await page.goto("/dashboard");
  const sidebar = page.getByRole("complementary", { name: "Article navigation" });
  const privateRow = sidebar.getByRole("button", { name: /Private allotment notes/i });
  await expect(privateRow.first()).toBeVisible();

  // Expire the session: the refresh cookie is gone and the next API call is a 401.
  await page.context().clearCookies();
  await page.route("**/api/v1/articles/*", (route) => route.fulfill({ status: 401 }), {
    times: 1,
  });
  await privateRow.first().click();
  await expect(page).toHaveURL(/\/login$/);

  // Record whether the first person's article is ever rendered from here on.
  await page.evaluate(() => {
    const seen = window as unknown as { sawPrivate: boolean };
    seen.sawPrivate = false;
    new MutationObserver(() => {
      if (document.body.innerText.includes("Private allotment notes"))
        seen.sawPrivate = true;
    }).observe(document.body, { childList: true, subtree: true, characterData: true });
  });
  await page.getByRole("button", { name: "Don't have an account? Sign up" }).click();
  await page.getByLabel("Name", { exact: true }).fill("Second Person");
  await page.getByLabel("Email", { exact: true }).fill(`second-${Date.now()}@test.dev`);
  await page.getByLabel("Password", { exact: true }).fill("local-switch-password-2");
  await page.getByRole("button", { name: "Sign up", exact: true }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByText("No articles yet")).toBeVisible();
  expect(
    await page.evaluate(() => (window as unknown as { sawPrivate: boolean }).sawPrivate),
  ).toBe(false);
});
