import { expect, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";

const neutralMessage = "If this email has a password account, a reset code will be sent.";

test("forgot password waits for hydration and submits by API on the first enabled interaction", async ({
  page,
}) => {
  let releaseScripts!: () => void;
  const scriptsReady = new Promise<void>((resolve) => {
    releaseScripts = resolve;
  });
  await page.route(/\/_next\/static\/.*\.js(?:\?.*)?$/, async (route) => {
    await scriptsReady;
    await route.continue();
  });
  await page.route("**/api/v1/auth/password/forgot", (route) =>
    route.fulfill({ status: 202, json: { message: neutralMessage } }),
  );
  await page.goto("/forgot-password", { waitUntil: "commit" });
  const email = page.getByLabel("Email", { exact: true });
  const submit = page.getByRole("button", { name: "Request reset code" });
  try {
    await expect(email).toBeDisabled();
    await expect(submit).toBeDisabled();
    await expect(page.locator("form")).toHaveAttribute("method", "post");
  } finally {
    releaseScripts();
  }
  await expect(email).toBeEnabled();
  await email.focus();
  await page.keyboard.type("writer@example.com");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("status")).toContainText(neutralMessage);
  await expect(page).toHaveURL(/\/forgot-password$/);
});

test("login recovery and account verification preserve linked Google sign-in", async ({
  page,
}) => {
  let accountSession = false;
  let emailVerified = false;
  await page.route("**/api/v1/auth/refresh", (route) =>
    route.fulfill(
      accountSession
        ? { json: { access_token: "mock-session", expires_in: 900 } }
        : { status: 401, json: {} },
    ),
  );
  await page.route("**/api/v1/auth/google/challenge", (route) =>
    route.fulfill({ json: { enabled: false } }),
  );
  await page.route("**/api/v1/auth/connections", (route) =>
    route.fulfill({ json: { password: true, google: true } }),
  );
  await page.route("**/api/v1/auth/me", (route) => {
    return route.fulfill({
      json: {
        id: 1,
        name: "Writer",
        email: "writer@example.com",
        created_at: "2026-10-09",
        email_verified: emailVerified,
      },
    });
  });
  await page.route("**/api/v1/auth/email/verification/request", (route) => {
    expect(route.request().headers().authorization).toBe("Bearer mock-session");
    return route.fulfill({
      status: 202,
      json: {
        message: "If email delivery is available, a verification code will be sent.",
      },
    });
  });
  await page.goto("/login");
  await page.getByRole("link", { name: "Forgot password?" }).click();
  await expect(page).toHaveURL(/\/forgot-password$/);
  await expect(
    page.getByRole("heading", { name: "Forgot your password?" }),
  ).toBeVisible();
  accountSession = true;
  await page.goto("/account");
  await expect(page.getByText("Email not verified", { exact: true })).toBeVisible();
  await expect(page.getByText("Google is linked to your account.")).toBeVisible();
  await page.getByRole("button", { name: "Send verification code" }).click();
  await expect(
    page.getByText("If email delivery is available, a verification code will be sent."),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Resend verification code" }),
  ).toBeEnabled();
  await expect(
    page.getByRole("link", { name: "Enter verification code" }),
  ).toHaveAttribute("href", "/verify-email");
  emailVerified = true;
  await page.getByRole("button", { name: "Refresh verification status" }).click();
  await expect(page.getByText("Email verified", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Resend verification code" }),
  ).toHaveCount(0);
  await expect(page.getByText("Google is linked to your account.")).toBeVisible();
});

for (const viewport of [
  { width: 1422, height: 588 },
  { width: 390, height: 844 },
]) {
  test(`recovery code forms are keyboard reachable at ${viewport.width}px`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    await page.route("**/api/v1/auth/password/forgot", (route) =>
      route.fulfill({ status: 202, json: { message: neutralMessage } }),
    );
    await page.route("**/api/v1/auth/password/reset", (route) =>
      route.fulfill({ json: { message: "Password reset." } }),
    );
    await page.route("**/api/v1/auth/email/verify", (route) =>
      route.fulfill({ json: { message: "Email verified." } }),
    );

    const response = await page.goto("/forgot-password");
    expect(response?.headers()["referrer-policy"]).toBe("no-referrer");
    // Next's dev server supplies no-cache; production retains configured no-store.
    expect(response?.headers()["cache-control"]).toMatch(/no-store|no-cache/);
    await expect(page.locator('meta[name="referrer"]')).toHaveAttribute(
      "content",
      "no-referrer",
    );
    await expect(
      page.getByRole("heading", { name: "Forgot your password?" }),
    ).toBeVisible();
    const email = page.getByLabel("Email", { exact: true });
    await expect(email).toBeEnabled();
    await email.focus();
    await page.keyboard.type("writer@example.com");
    await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: "Request reset code" })).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("status")).toContainText(neutralMessage);

    await page.goto("/reset-password");
    await expect(page.getByLabel("Reset code", { exact: true })).toBeVisible();
    if (process.env.SCREENSHOT_DIR) {
      const folder = path.resolve(process.env.SCREENSHOT_DIR);
      await mkdir(folder, { recursive: true });
      await page.screenshot({
        path: path.join(folder, `reset-${viewport.width}.png`),
        fullPage: true,
      });
    }
    await page.getByLabel("Reset code", { exact: true }).fill("manual-reset-code");
    await page.getByLabel("New password", { exact: true }).fill("NewPassword123");
    await page.keyboard.press("Tab");
    await expect(page.getByLabel("Repeat new password")).toBeFocused();
    await page.keyboard.type("NewPassword123");
    await page.keyboard.press("Tab");
    const reset = page.getByRole("button", { name: "Reset password", exact: true });
    await expect(reset).toBeFocused();
    await reset.scrollIntoViewIfNeeded();
    const box = await reset.boundingBox();
    expect(box!.y + box!.height).toBeLessThanOrEqual(viewport.height);
    expect(
      await page.evaluate(() => ({ width: innerWidth, height: innerHeight })),
    ).toEqual(viewport);
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBe(true);
    await page.keyboard.press("Enter");
    await expect(page.getByRole("status")).toContainText("Sign in again");
    await expect(page.getByRole("link", { name: "Go to login" })).toHaveAttribute(
      "href",
      "/login",
    );
    await expect(page).toHaveURL(/\/reset-password$/);

    await page.goto("/verify-email");
    await page.getByLabel("Verification code").fill("manual-verification-code");
    await page.keyboard.press("Tab");
    await expect(
      page.getByRole("button", { name: "Verify email", exact: true }),
    ).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("status")).toContainText("email is verified");
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBe(true);
  });
}

test("fragment reset strips the URL and keeps the code through validation and retry", async ({
  page,
}) => {
  let calls = 0;
  const bodies: unknown[] = [];
  const urls: string[] = [];
  page.on("request", (request) => urls.push(request.url()));
  await page.route("**/api/v1/auth/password/reset", async (route) => {
    bodies.push(route.request().postDataJSON());
    calls += 1;
    await route.fulfill(
      calls === 1
        ? {
            status: 503,
            json: {
              error: {
                code: "TEMPORARY",
                message: "Try again later.",
                request_id: "mock",
              },
            },
          }
        : { json: { message: "Password reset." } },
    );
  });
  await page.goto("/reset-password#token=synthetic_fragment_reset_code");
  await expect(page).toHaveURL(/\/reset-password$/);
  await expect(page.getByLabel("Reset code", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Reset password", exact: true }).click();
  await expect(page.getByText("At least 8 characters", { exact: true })).toBeVisible();
  expect(calls).toBe(0);
  await page.getByLabel("New password", { exact: true }).fill("NewPassword123");
  await page.getByLabel("Repeat new password").fill("NewPassword123");
  await page.getByRole("button", { name: "Reset password", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("unavailable");
  await page.getByRole("button", { name: "Reset password", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Sign in again");
  expect(bodies).toEqual(
    Array(2).fill({ token: "synthetic_fragment_reset_code", password: "NewPassword123" }),
  );
  expect(urls.every((url) => !url.includes("synthetic_fragment_reset_code"))).toBe(true);
  expect(
    await page.evaluate(
      () => `${JSON.stringify(localStorage)}${JSON.stringify(sessionStorage)}`,
    ),
  ).not.toContain("synthetic_fragment_reset_code");
});

test("invalid manual verification allows a fresh code and consumes nothing on page load", async ({
  page,
}) => {
  let calls = 0;
  await page.route("**/api/v1/auth/email/verify", async (route) => {
    calls += 1;
    await route.fulfill(
      calls === 1
        ? {
            status: 400,
            json: {
              error: {
                code: "INVALID_TOKEN",
                message: "Invalid code.",
                request_id: "mock",
              },
            },
          }
        : { json: { message: "Email verified." } },
    );
  });
  await page.goto("/verify-email?token=unsupported_query_code");
  await expect(page).toHaveURL(/\/verify-email$/);
  expect(calls).toBe(0);
  await page.getByRole("button", { name: "Verify email", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "Paste the full verification code",
  );
  expect(calls).toBe(0);
  await page.getByLabel("Verification code").fill("expired-code");
  await page.getByRole("button", { name: "Verify email", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "invalid, expired, or already used",
  );
  await page.getByLabel("Verification code").fill("fresh-code");
  await page.getByRole("button", { name: "Verify email", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("email is verified");
  expect(calls).toBe(2);
});
