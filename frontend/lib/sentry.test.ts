import type { BrowserOptions } from "@sentry/browser";
import { beforeEach, describe, expect, it, vi } from "vitest";

const sentry = vi.hoisted(() => ({ init: vi.fn(), captureException: vi.fn() }));
vi.mock("@sentry/browser", () => sentry);

import { initSentry, reportError, withoutQuery } from "./sentry";

function initOptions(): BrowserOptions {
  initSentry("https://key@o1.ingest.sentry.io/2");
  return sentry.init.mock.calls[0][0];
}

describe("initSentry", () => {
  beforeEach(() => vi.clearAllMocks());

  it("does nothing without a DSN", () => {
    expect(initSentry("")).toBe(false);
    expect(sentry.init).not.toHaveBeenCalled();
  });

  it("sends errors only, with no personal data", () => {
    expect(initSentry("https://key@o1.ingest.sentry.io/2")).toBe(true);

    expect(sentry.init).toHaveBeenCalledWith(
      expect.objectContaining({
        dsn: "https://key@o1.ingest.sentry.io/2",
        tracesSampleRate: 0,
        dataCollection: {
          userInfo: false,
          cookies: false,
          httpHeaders: false,
          httpBodies: [],
          urlQueryParams: false,
        },
      }),
    );
  });

  it("keeps reset-link tokens out of navigation breadcrumbs", () => {
    const { beforeBreadcrumb } = initOptions();

    const crumb = beforeBreadcrumb!({
      category: "navigation",
      data: {
        from: "/reset-password#token=secret-reset-token-123",
        to: "/reset-password",
      },
    });
    const fetch = beforeBreadcrumb!({
      category: "fetch",
      data: { url: "/api/v1/articles/1/photos?query=old+books", status_code: 500 },
    });

    expect(crumb?.data).toEqual({ from: "/reset-password", to: "/reset-password" });
    expect(fetch?.data).toEqual({ url: "/api/v1/articles/1/photos", status_code: 500 });
  });

  it("keeps the query and fragment out of the reported page URL", () => {
    const { beforeSend } = initOptions();

    const event = beforeSend!(
      {
        type: undefined,
        request: {
          url: "https://searchscribe.test/verify-email?x=1#token=secret-verify-token-456",
          query_string: "x=1",
        },
      },
      {},
    );

    expect(event).toMatchObject({
      request: { url: "https://searchscribe.test/verify-email" },
    });
    expect(JSON.stringify(event)).not.toContain("secret");
    expect(JSON.stringify(event)).not.toContain("x=1");
  });

  it("reports an error through the SDK", () => {
    const error = new Error("render failed");
    reportError(error);
    expect(sentry.captureException).toHaveBeenCalledWith(error);
  });
});

describe("withoutQuery", () => {
  it.each([
    ["https://a.test/p?q=1#t=2", "https://a.test/p"],
    ["/reset-password#token=abc", "/reset-password"],
    ["/dashboard", "/dashboard"],
  ])("%s -> %s", (url, expected) => {
    expect(withoutQuery(url)).toBe(expected);
  });
});
