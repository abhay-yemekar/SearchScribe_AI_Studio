import { afterEach, describe, expect, it, vi } from "vitest";

import { restoreVersion } from "./articles";
import { clearAccessToken, setAccessToken } from "@/lib/auth/token-store";

describe("restoreVersion", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    clearAccessToken();
  });

  it("sends the version being viewed so a newer one is refused instead of overwritten", async () => {
    setAccessToken("token-1", 900);
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({}), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(restoreVersion(5, 2, 3)).rejects.toBeTruthy();

    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/v1/articles/5/versions/2/restore");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ base_version: 3 });
  });
});
