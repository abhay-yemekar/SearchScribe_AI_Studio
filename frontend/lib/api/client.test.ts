import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch, refreshOnce, UnauthorizedError } from "./client";
import { ApiError } from "./errors";
import { clearAccessToken, setAccessToken } from "@/lib/auth/token-store";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const errorEnvelope = (code: string, message: string) => ({
  error: { code, message, request_id: "req-1" },
});

describe("apiFetch", () => {
  beforeEach(() => {
    setAccessToken("token-1", 900);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    clearAccessToken();
  });

  it("returns parsed JSON on success and attaches the bearer token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { hello: "world" }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await apiFetch<{ hello: string }>("/api/v1/x");

    expect(result).toEqual({ hello: "world" });
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Headers).get("Authorization")).toBe("Bearer token-1");
  });

  it("shares a refresh request between bootstrap and an expired API request", async () => {
    let finishRefresh!: (response: Response) => void;
    const pending = new Promise<Response>((resolve) => {
      finishRefresh = resolve;
    });
    const fetchMock = vi.fn().mockImplementation((path: string, init: RequestInit) => {
      if (path === "/api/v1/auth/refresh") return pending;
      const token = (init.headers as Headers).get("Authorization");
      return Promise.resolve(
        token === "Bearer fresh"
          ? jsonResponse(200, { ok: true })
          : jsonResponse(401, errorEnvelope("AUTHENTICATION_REQUIRED", "expired")),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    const bootstrap = refreshOnce();
    const request = apiFetch("/api/v1/articles");
    await Promise.resolve();
    finishRefresh(jsonResponse(200, { access_token: "fresh", expires_in: 900 }));
    await expect(bootstrap).resolves.toBe(true);
    await expect(request).resolves.toEqual({ ok: true });
    expect(
      fetchMock.mock.calls.filter(([path]) => path === "/api/v1/auth/refresh"),
    ).toHaveLength(1);
  });

  it("wraps error envelopes into ApiError with code and request id", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(404, errorEnvelope("NOT_FOUND", "nope"))),
    );

    const error = (await apiFetch("/api/v1/x").catch((e) => e)) as ApiError;

    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe("NOT_FOUND");
    expect(error.requestId).toBe("req-1");
    expect(error.status).toBe(404);
  });

  it("falls back to a generic error for non-JSON responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(new Response("<html>gateway error</html>", { status: 502 })),
    );

    const error = (await apiFetch("/api/v1/x").catch((e) => e)) as ApiError;

    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe("HTTP_502");
  });

  it("silently refreshes once on 401 and retries the request", async () => {
    setAccessToken("stale-token", 900);
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(401, errorEnvelope("AUTHENTICATION_REQUIRED", "x")),
      )
      .mockResolvedValueOnce(
        jsonResponse(200, { access_token: "fresh", expires_in: 900 }),
      )
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await apiFetch<{ ok: boolean }>("/api/v1/articles");

    expect(result).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    // Retry used the refreshed token.
    const [, retryInit] = fetchMock.mock.calls[2] as [string, RequestInit];
    expect((retryInit.headers as Headers).get("Authorization")).toBe("Bearer fresh");
  });

  it("throws UnauthorizedError and clears the token when refresh fails", async () => {
    setAccessToken("stale-token", 900);
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(401, errorEnvelope("AUTHENTICATION_REQUIRED", "x")),
      )
      .mockResolvedValueOnce(
        jsonResponse(401, errorEnvelope("AUTHENTICATION_REQUIRED", "x")),
      );
    vi.stubGlobal("fetch", fetchMock);

    const error = await apiFetch("/api/v1/articles").catch((e) => e);

    expect(error).toBeInstanceOf(UnauthorizedError);
  });

  it("does not attempt refresh for auth endpoints", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse(401, errorEnvelope("AUTHENTICATION_REQUIRED", "x")),
        ),
    );

    const error = await apiFetch("/api/v1/auth/login", {
      method: "POST",
      body: "{}",
    }).catch((e) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(vi.mocked(globalThis.fetch)).toHaveBeenCalledTimes(1);
  });
});
