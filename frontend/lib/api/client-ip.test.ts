import { afterEach, describe, expect, it, vi } from "vitest";
import { unstable_doesMiddlewareMatch } from "next/experimental/testing/server";
import { NextRequest } from "next/server";

import { apiRequestHeaders, CLIENT_IP_HEADER, PROXY_SECRET_HEADER } from "./client-ip";
import { config, proxy } from "@/proxy";

const SECRET = "s".repeat(48);

function browserHeaders(extra: Record<string, string> = {}): Headers {
  return new Headers({ cookie: "a=b", "x-real-ip": "203.0.113.7", ...extra });
}

describe("apiRequestHeaders", () => {
  it("forwards Vercel's client IP with the shared secret", () => {
    const headers = apiRequestHeaders(browserHeaders(), {
      secret: SECRET,
      onVercel: true,
    });

    expect(headers.get(CLIENT_IP_HEADER)).toBe("203.0.113.7");
    expect(headers.get(PROXY_SECRET_HEADER)).toBe(SECRET);
    expect(headers.get("cookie")).toBe("a=b");
  });

  it("replaces a client IP and secret that the browser sent itself", () => {
    const spoofed = browserHeaders({
      [CLIENT_IP_HEADER]: "198.51.100.1",
      [PROXY_SECRET_HEADER]: "guess",
    });

    const headers = apiRequestHeaders(spoofed, { secret: SECRET, onVercel: true });

    expect(headers.get(CLIENT_IP_HEADER)).toBe("203.0.113.7");
    expect(headers.get(PROXY_SECRET_HEADER)).toBe(SECRET);
  });

  it.each([
    ["no secret is configured", { secret: undefined, onVercel: true }],
    ["the proxy is not on Vercel", { secret: SECRET, onVercel: false }],
  ])("drops spoofed headers and forwards nothing when %s", (_, env) => {
    const spoofed = browserHeaders({
      [CLIENT_IP_HEADER]: "198.51.100.1",
      [PROXY_SECRET_HEADER]: "guess",
    });

    const headers = apiRequestHeaders(spoofed, env);

    expect(headers.has(CLIENT_IP_HEADER)).toBe(false);
    expect(headers.has(PROXY_SECRET_HEADER)).toBe(false);
  });

  it("forwards nothing when Vercel gave no client IP", () => {
    const headers = apiRequestHeaders(new Headers(), { secret: SECRET, onVercel: true });

    expect(headers.has(CLIENT_IP_HEADER)).toBe(false);
    expect(headers.has(PROXY_SECRET_HEADER)).toBe(false);
  });
});

describe("proxy", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("runs only for API calls", () => {
    expect(unstable_doesMiddlewareMatch({ config, url: "/api/v1/auth/refresh" })).toBe(
      true,
    );
    expect(unstable_doesMiddlewareMatch({ config, url: "/dashboard" })).toBe(false);
  });

  it("passes the client IP upstream as a request header, not to the browser", () => {
    vi.stubEnv("VERCEL", "1");
    vi.stubEnv("PROXY_SHARED_SECRET", SECRET);
    const request = new NextRequest("https://example.test/api/v1/auth/login", {
      headers: browserHeaders(),
    });

    const response = proxy(request);

    expect(response.headers.get(`x-middleware-request-${CLIENT_IP_HEADER}`)).toBe(
      "203.0.113.7",
    );
    expect(response.headers.get(`x-middleware-request-${PROXY_SECRET_HEADER}`)).toBe(
      SECRET,
    );
    expect(response.headers.has(CLIENT_IP_HEADER)).toBe(false);
  });
});
