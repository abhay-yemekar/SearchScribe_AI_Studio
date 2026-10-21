import { afterEach, describe, expect, it, vi } from "vitest";

import {
  clearAccessToken,
  onIdentityChange,
  setAccessToken,
  subscribe,
} from "./token-store";

// Only the payload matters here; the API, not the browser, verifies signatures.
function tokenFor(userId: number, version = 0): string {
  const payload = btoa(JSON.stringify({ sub: String(userId), sv: version }))
    .replace(/=+$/, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
  return `header.${payload}.signature`;
}

describe("onIdentityChange", () => {
  afterEach(() => clearAccessToken());

  it("fires when another user signs in on the same tab, even after the session expired", () => {
    setAccessToken(tokenFor(101));
    const listener = vi.fn();
    const stop = onIdentityChange(listener);

    clearAccessToken();
    setAccessToken(tokenFor(202));

    expect(listener).toHaveBeenCalledTimes(1);
    stop();
  });

  it("stays quiet for refreshes and for the same user signing back in", () => {
    setAccessToken(tokenFor(303));
    const listener = vi.fn();
    const stop = onIdentityChange(listener);

    setAccessToken(tokenFor(303, 1));
    clearAccessToken();
    setAccessToken(tokenFor(303, 1));

    expect(listener).not.toHaveBeenCalled();
    stop();
  });

  it("runs before components see the new token, so nothing renders old data", () => {
    setAccessToken(tokenFor(404));
    const order: string[] = [];
    const stop = onIdentityChange(() => order.push("identity"));
    const unsubscribe = subscribe(() => order.push("token"));

    setAccessToken(tokenFor(505));

    expect(order).toEqual(["identity", "token"]);
    unsubscribe();
    stop();
  });
});
