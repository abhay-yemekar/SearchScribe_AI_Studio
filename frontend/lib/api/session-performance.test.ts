import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchCurrentUser, login } from "./auth";
import { refreshOnce } from "./client";
import { clearAccessToken, setAccessToken } from "@/lib/auth/token-store";

const user = {
  id: 1,
  name: "Writer",
  email: "writer@example.com",
  email_verified: false,
  created_at: "2026-10-14",
};
const payload = {
  access_token: "signed-in",
  expires_in: 900,
  token_type: "bearer",
  user,
};
const response = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
afterEach(() => {
  clearAccessToken();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("session request economy", () => {
  it("uses the verified login response without an extra profile request", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(payload));
    vi.stubGlobal("fetch", fetcher);
    await login({ email: user.email, password: "test-only-password" });
    expect(await fetchCurrentUser()).toEqual(user);
    expect(await fetchCurrentUser()).toEqual(user);
    expect(fetcher).toHaveBeenCalledOnce();
    expect(fetcher.mock.calls[0][0]).toBe("/api/v1/auth/login");
  });
  it("restores both identity and profile in one refresh request", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(payload));
    vi.stubGlobal("fetch", fetcher);
    expect(await refreshOnce()).toBe(true);
    expect(await fetchCurrentUser()).toEqual(user);
    expect(fetcher).toHaveBeenCalledOnce();
    expect(fetcher.mock.calls[0][0]).toBe("/api/v1/auth/refresh");
  });
  it("shares concurrent profile loads, permits explicit refresh, and isolates a new identity", async () => {
    setAccessToken("first-user", 900);
    const fetcher = vi.fn().mockImplementation(() => Promise.resolve(response(user)));
    vi.stubGlobal("fetch", fetcher);
    await Promise.all([fetchCurrentUser(), fetchCurrentUser(), fetchCurrentUser()]);
    expect(fetcher).toHaveBeenCalledOnce();
    await fetchCurrentUser({ force: true });
    expect(fetcher).toHaveBeenCalledTimes(2);
    setAccessToken("second-user", 900);
    await fetchCurrentUser();
    expect(fetcher).toHaveBeenCalledTimes(3);
  });
  it("expires the profile and never caches a failed response", async () => {
    let now = 100000;
    vi.spyOn(Date, "now").mockImplementation(() => now);
    setAccessToken("timed-session", 900);
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        response(
          {
            error: {
              code: "SERVICE_UNAVAILABLE",
              message: "Offline",
              request_id: "test",
            },
          },
          503,
        ),
      )
      .mockImplementation(() => Promise.resolve(response(user)));
    vi.stubGlobal("fetch", fetcher);
    await expect(fetchCurrentUser()).rejects.toThrow("Offline");
    await fetchCurrentUser();
    now += 60001;
    await fetchCurrentUser();
    expect(fetcher).toHaveBeenCalledTimes(3);
  });
});
