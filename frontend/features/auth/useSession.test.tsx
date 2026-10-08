import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clearAccessToken, setAccessToken } from "@/lib/auth/token-store";
import { fetchCurrentUser } from "@/lib/api/auth";
import { useSession } from "./useSession";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@tanstack/react-query", () => ({ useQueryClient: () => ({ clear: vi.fn() }) }));
vi.mock("@/lib/api/auth", () => ({ fetchCurrentUser: vi.fn(), logout: vi.fn() }));

const user = {
  id: 1,
  name: "Writer",
  email: "writer@example.com",
  created_at: "2026-10-08",
};
let clock = 1_000_000;

function response(status: number) {
  return new Response(JSON.stringify({}), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function mount(publicView: boolean) {
  const hook = renderHook(() => useSession({ publicView }));
  await waitFor(() => expect(hook.result.current.bootstrapping).toBe(false));
  return hook;
}

describe("public session bootstrap", () => {
  beforeEach(() => {
    clock += 60_000;
    vi.spyOn(Date, "now").mockImplementation(() => clock);
    clearAccessToken();
    vi.mocked(fetchCurrentUser).mockResolvedValue(user);
  });

  afterEach(() => {
    clearAccessToken();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("avoids another refresh on public navigation after 401, then retries after expiry", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(401));
    vi.stubGlobal("fetch", fetchMock);
    (await mount(true)).unmount();
    (await mount(true)).unmount();
    expect(fetchMock).toHaveBeenCalledOnce();
    clock += 30_001;
    (await mount(true)).unmount();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("still checks the refresh cookie on login/protected routes after a public 401", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(401));
    vi.stubGlobal("fetch", fetchMock);
    (await mount(true)).unmount();
    (await mount(false)).unmount();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("recognizes a new token immediately and clears the public absence memo", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(401));
    vi.stubGlobal("fetch", fetchMock);
    (await mount(true)).unmount();
    act(() => setAccessToken("signed-in", 900));
    const signedIn = await mount(true);
    expect(signedIn.result.current.user).toEqual(user);
    expect(fetchMock).toHaveBeenCalledOnce();
    signedIn.unmount();
    act(() => clearAccessToken());
    (await mount(true)).unmount();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it.each([429, 500, 503])("retries public bootstrap after HTTP %s", async (status) => {
    const fetchMock = vi.fn().mockResolvedValue(response(status));
    vi.stubGlobal("fetch", fetchMock);
    (await mount(true)).unmount();
    (await mount(true)).unmount();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("retries public bootstrap after network failure", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error("offline"));
    vi.stubGlobal("fetch", fetchMock);
    (await mount(true)).unmount();
    (await mount(true)).unmount();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
