import { render } from "@testing-library/react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { act } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { z } from "zod";

import { clearAccessToken, setAccessToken } from "@/lib/auth/token-store";
import Providers from "./providers";

function tokenFor(userId: number): string {
  const payload = btoa(JSON.stringify({ sub: String(userId) })).replace(/=+$/, "");
  return `header.${payload}.signature`;
}

function renderWithClient() {
  let client!: QueryClient;
  function Capture() {
    client = useQueryClient();
    return null;
  }
  render(
    <Providers>
      <Capture />
    </Providers>,
  );
  return client;
}

describe("Providers", () => {
  afterEach(() => clearAccessToken());

  it("turns off Zod's eval probe, which the CSP would report on every page", () => {
    expect(z.config().jitless).toBe(true);
  });

  it("drops the previous user's cached articles when someone else signs in", () => {
    act(() => setAccessToken(tokenFor(1)));
    const client = renderWithClient();
    client.setQueryData(["articles"], { pages: [{ items: [{ id: 7 }] }] });
    client.setQueryData(["workspace-draft", 1], { draft: "unsaved" });

    act(() => {
      clearAccessToken(); // the first session expired
      setAccessToken(tokenFor(2));
    });

    expect(client.getQueryData(["articles"])).toBeUndefined();
    expect(client.getQueryData(["workspace-draft", 1])).toBeUndefined();
  });

  it("keeps the cache, including unsaved drafts, when the same user signs back in", () => {
    act(() => setAccessToken(tokenFor(3)));
    const client = renderWithClient();
    client.setQueryData(["workspace-draft", 3], { draft: "unsaved" });

    act(() => {
      clearAccessToken();
      setAccessToken(tokenFor(3));
    });

    expect(client.getQueryData(["workspace-draft", 3])).toEqual({ draft: "unsaved" });
  });
});
