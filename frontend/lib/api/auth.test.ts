import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  forgotPassword,
  requestEmailVerification,
  resetPassword,
  verifyEmail,
  addPassword,
  changePassword,
  passwordAddChallenge,
} from "./auth";
import { clearAccessToken, getSnapshot, setAccessToken } from "@/lib/auth/token-store";
import { userSchema } from "./schemas";

beforeEach(() => setAccessToken("existing-session", 900));
afterEach(() => {
  clearAccessToken();
  vi.unstubAllGlobals();
});

function mockRequest() {
  const fetchMock = vi.fn().mockImplementation(() =>
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
  it("loads password-add challenges with current authentication and no browser caching", async () => {
    const fetchMock = mockRequest();
    await passwordAddChallenge();
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/auth/password/add/challenge");
    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      cache: "no-store",
      referrerPolicy: "no-referrer",
      credentials: "include",
    });
    expect(fetchMock.mock.calls[0][1].headers.get("Authorization")).toBe(
      "Bearer existing-session",
    );
  });

  it("sends Google proof and current-password secrets only in authenticated uncached POST bodies", async () => {
    const fetchMock = mockRequest();
    await addPassword("fresh-google-proof", "NewPassword123");
    await changePassword("OldPassword123", "NewPassword123");
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/auth/password/add",
      "/api/v1/auth/password/change",
    ]);
    expect(fetchMock.mock.calls[0][1].body).toBe(
      JSON.stringify({ credential: "fresh-google-proof", password: "NewPassword123" }),
    );
    expect(fetchMock.mock.calls[1][1].body).toBe(
      JSON.stringify({ current_password: "OldPassword123", password: "NewPassword123" }),
    );
    for (const [, init] of fetchMock.mock.calls) {
      expect(init).toMatchObject({
        method: "POST",
        cache: "no-store",
        referrerPolicy: "no-referrer",
      });
      expect(init.headers.get("Authorization")).toBe("Bearer existing-session");
    }
  });

  it("does not treat a malformed message as mutation failure after a successful HTTP response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ unexpected: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    await expect(
      changePassword("OldPassword123", "NewPassword123"),
    ).resolves.toBeUndefined();
  });
  it.each(["", '{"message":', "<html>Proxy response</html>"])(
    "accepts HTTP mutation success despite an unusable body: %s",
    async (body) => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(new Response(body, { status: 200 })),
      );
      await expect(
        changePassword("OldPassword123", "NewPassword123"),
      ).resolves.toBeUndefined();
    },
  );

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
