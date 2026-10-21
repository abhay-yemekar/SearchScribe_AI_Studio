import { expect, test, type Page } from "@playwright/test";

// Accounts and articles here belong only to the disposable mock-provider stack.
async function accountWithArticles(page: Page, topics: string[]) {
  const signup = await page.request.post("/api/v1/auth/signup", {
    data: {
      name: "Delete Test",
      email: `delete-${Date.now()}@test.dev`,
      password: "local-delete-password-1",
    },
  });
  expect(signup.status()).toBe(201);
  const headers = { Authorization: `Bearer ${(await signup.json()).access_token}` };
  for (const query of topics) {
    const generated = await page.request.post("/api/v1/articles", {
      headers,
      data: { query },
    });
    expect(generated.status()).toBe(201);
  }
  return headers;
}

test("deletes an article from the keyboard, undoes it, then deletes it for real", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.clock.install();
  const headers = await accountWithArticles(page, [
    "Composting at home",
    "Growing herbs on a balcony",
  ]);
  await page.goto("/dashboard");

  const sidebar = page.getByRole("complementary", { name: "Article navigation" });
  const row = sidebar.getByRole("button", { name: /^(?!Delete ).*Composting at home/i });
  const remove = sidebar.getByRole("button", { name: /^Delete .*Composting at home/i });
  const undo = page.getByRole("button", { name: "Undo" });

  // The delete button follows its row in the tab order and is visible when focused.
  await row.focus();
  await page.keyboard.press("Tab");
  await expect(remove).toBeFocused();
  await expect
    .poll(() => remove.evaluate((el) => getComputedStyle(el).opacity))
    .toBe("1");

  await page.keyboard.press("Enter");
  await expect(row).toHaveCount(0);
  await expect(undo).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(row).toBeVisible();

  await row.focus();
  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");
  await expect(undo).toBeVisible();
  await page.clock.fastForward(11_000);
  await expect(undo).toHaveCount(0);
  await expect
    .poll(async () => {
      const list = await page.request.get("/api/v1/articles", { headers });
      return (await list.json()).items.map((item: { query: string }) => item.query);
    })
    .toEqual(["Growing herbs on a balcony"]);
  await expect(row).toHaveCount(0);
});
