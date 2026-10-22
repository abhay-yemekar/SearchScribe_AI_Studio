import { unstable_getResponseFromNextConfig } from "next/experimental/testing/server";
import { describe, expect, it } from "vitest";

import nextConfig from "../next.config.mjs";
import { contentSecurityPolicy, isAppPath } from "./security-headers.mjs";

const directive = (csp: string, name: string) =>
  csp.split("; ").find((part) => part.startsWith(`${name} `));

async function headersFor(path: string): Promise<Headers> {
  const response = await unstable_getResponseFromNextConfig({
    url: `https://searchscribe.test${path}`,
    nextConfig,
  });
  return response.headers;
}

describe("contentSecurityPolicy", () => {
  it("lets only nonce-signed scripts run on app pages", () => {
    const csp = contentSecurityPolicy({ nonce: "abc123", dev: false });

    expect(directive(csp, "script-src")).toBe(
      "script-src 'self' 'nonce-abc123' 'strict-dynamic'",
    );
    expect(csp).not.toContain("unsafe-eval");
  });

  it("blocks framing, plugins, base rewrites and foreign form posts everywhere", () => {
    for (const csp of [
      contentSecurityPolicy({ nonce: "n", dev: false }),
      contentSecurityPolicy({ dev: false }),
    ]) {
      for (const rule of [
        "frame-ancestors 'none'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "default-src 'self'",
      ]) {
        expect(csp).toContain(rule);
      }
    }
  });

  it("allows Google sign-in and Wikimedia photos, and nothing else external", () => {
    const csp = contentSecurityPolicy({ nonce: "n", dev: false });

    expect(directive(csp, "frame-src")).toBe(
      "frame-src https://accounts.google.com/gsi/",
    );
    expect(directive(csp, "connect-src")).toBe(
      "connect-src 'self' https://accounts.google.com/gsi/",
    );
    expect(directive(csp, "img-src")).toBe(
      "img-src 'self' data: blob: https://upload.wikimedia.org https://thumb.wikimedia.org",
    );
  });

  it("lets the browser report to Sentry only when a DSN is configured", () => {
    const withSentry = contentSecurityPolicy({
      nonce: "n",
      dev: false,
      sentryDsn: "https://publickey@o123.ingest.de.sentry.io/456",
    });
    const without = contentSecurityPolicy({ nonce: "n", dev: false, sentryDsn: "" });
    const bogus = contentSecurityPolicy({ dev: false, sentryDsn: "not a url" });

    expect(directive(withSentry, "connect-src")).toBe(
      "connect-src 'self' https://accounts.google.com/gsi/ https://o123.ingest.de.sentry.io",
    );
    expect(directive(without, "connect-src")).not.toContain("sentry");
    expect(directive(bogus, "connect-src")).not.toContain("not");
  });

  it("adds what Next's dev server needs only in development", () => {
    const csp = contentSecurityPolicy({ nonce: "n", dev: true });

    expect(directive(csp, "script-src")).toContain("'unsafe-eval'");
    expect(directive(csp, "connect-src")).toContain("ws:");
  });
});

describe("isAppPath", () => {
  it.each([
    ["/dashboard", true],
    ["/account", true],
    ["/login", true],
    ["/reset-password", true],
    ["/", false],
    ["/features", false],
    ["/accountability", false],
  ])("%s -> %s", (path, expected) => {
    expect(isAppPath(path)).toBe(expected);
  });
});

describe("next.config headers", () => {
  it.each(["/", "/features", "/how-it-works", "/example", "/privacy"])(
    "public page %s gets the fixed CSP and the base headers",
    async (path) => {
      const headers = await headersFor(path);

      expect(headers.get("content-security-policy")).toBe(
        contentSecurityPolicy({ dev: false }),
      );
      expect(headers.get("x-frame-options")).toBe("DENY");
      expect(headers.get("x-content-type-options")).toBe("nosniff");
      expect(headers.get("referrer-policy")).toBe("strict-origin-when-cross-origin");
    },
  );

  it.each(["/dashboard", "/account", "/login", "/reset-password"])(
    "app page %s gets the base headers; proxy.ts adds its nonce CSP",
    async (path) => {
      const headers = await headersFor(path);

      expect(headers.get("content-security-policy")).toBeNull();
      expect(headers.get("x-frame-options")).toBe("DENY");
      expect(headers.get("x-content-type-options")).toBe("nosniff");
    },
  );

  it("recovery pages keep no-referrer and no-store", async () => {
    const headers = await headersFor("/reset-password");

    expect(headers.get("referrer-policy")).toBe("no-referrer");
    expect(headers.get("cache-control")).toBe("no-store");
  });

  it("leaves API responses to the backend's own headers", async () => {
    const headers = await headersFor("/api/v1/health");

    expect(headers.get("x-frame-options")).toBeNull();
    expect(headers.get("content-security-policy")).toBeNull();
  });
});
