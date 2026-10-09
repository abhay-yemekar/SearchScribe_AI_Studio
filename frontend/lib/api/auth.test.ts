import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  forgotPassword,
  requestEmailVerification,
  resetPassword,
  verifyEmail,
} from "./auth";
import { clearAccessToken, getSnapshot, setAccessToken } from "@/lib/auth/token-store";
import { userSchema } from "./schemas";

beforeEach(() => setAccessToken("existing-session", 900));
afterEach(() => {
  clearAccessToken();
  vi.unstubAllGlobals();
});

function mockRequest() {
  const fetchMock = vi
    .fn()
    .mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify({ message: "Request complete." }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("recovery API requests", () => {
  it("sends reset secrets only in an uncached POST body and clears the existing session", async () => {
    const fetchMock = mockRequest();
    await resetPassword("opaque-code", "NewPassword123");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/auth/password/reset");
    expect(init).toMatchObject({
      method: "POST",
      body: JSON.stringify({ token: "opaque-code", password: "NewPassword123" }),
      referrerPolicy: "no-referrer",
      cache: "no-store",
    });
    expect(init.headers.has("Authorization")).toBe(false);
    expect(getSnapshot()).toBeNull();
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("does not attach an existing session to forgot or verify requests", async () => {
    const fetchMock = mockRequest();
    await forgotPassword("writer@example.com");
    await verifyEmail("verification-code");
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/auth/password/forgot",
      "/api/v1/auth/email/verify",
    ]);
    for (const [, init] of fetchMock.mock.calls)
      expect(init.headers.has("Authorization")).toBe(false);
    expect(fetchMock.mock.calls[1][1].body).toBe(
      JSON.stringify({ token: "verification-code" }),
    );
    expect(getSnapshot()).toBe("existing-session");
  });

  it("authenticates verification requests for the current account", async () => {
    const fetchMock = mockRequest();
    await requestEmailVerification();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/auth/email/verification/request");
    expect(fetchMock.mock.calls[0][1].headers.get("Authorization")).toBe(
      "Bearer existing-session",
    );
  });

  it("keeps older user payloads compatible without claiming verified email", () => {
    const user = userSchema.parse({
      id: 1,
      name: "Writer",
      email: "writer@example.com",
      created_at: "2026-10-09",
    });
    expect(user.email_verified).toBe(false);
  });
});
