import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, afterEach, vi, test, expect } from "vitest";
import GoogleSignIn from "./GoogleSignIn";

vi.mock("@/lib/api/client", () => ({ apiFetch: vi.fn() }));
vi.mock("next/script", () => ({
  default: ({ onReady }: { onReady: () => void }) => (
    <button type="button" onClick={onReady}>
      Load Google script
    </button>
  ),
}));
import { apiFetch } from "@/lib/api/client";

beforeEach(() => vi.resetAllMocks());
afterEach(() => {
  delete (window as Window & { google?: unknown }).google;
});

function installSdk() {
  const initialize = vi.fn();
  Object.assign(window, {
    google: { accounts: { id: { initialize, renderButton: vi.fn() } } },
  });
  return initialize;
}

async function readySdk(initialize: ReturnType<typeof vi.fn>) {
  fireEvent.click(await screen.findByRole("button", { name: "Load Google script" }));
  await waitFor(() => expect(initialize).toHaveBeenCalled());
  return initialize.mock.calls.at(-1)![0].callback as (response: {
    credential: string;
  }) => void;
}

test("unconfigured Google sign-in does not show a nonworking button", async () => {
  vi.mocked(apiFetch).mockResolvedValue({ enabled: false });
  const onError = vi.fn();
  const { container } = render(<GoogleSignIn onCredential={vi.fn()} onError={onError} />);
  await act(async () => {});
  expect(container).toBeEmptyDOMElement();
  expect(onError).not.toHaveBeenCalled();
});

test("login can explain explicitly disabled Google sign-in without a fake button", async () => {
  vi.mocked(apiFetch).mockResolvedValue({ enabled: false });
  const onError = vi.fn();
  const { getByRole, queryByRole } = render(
    <GoogleSignIn onCredential={vi.fn()} onError={onError} showUnavailableMessage />,
  );
  await waitFor(() =>
    expect(getByRole("status")).toHaveTextContent(
      "Google sign-in is unavailable on this instance. Continue with email and password.",
    ),
  );
  expect(queryByRole("button")).not.toBeInTheDocument();
  expect(onError).not.toHaveBeenCalled();
});

test("Google outage leaves password route available with clear feedback", async () => {
  vi.mocked(apiFetch).mockRejectedValue(new Error("offline"));
  const onError = vi.fn();
  render(<GoogleSignIn onCredential={vi.fn()} onError={onError} />);
  await waitFor(() =>
    expect(onError).toHaveBeenCalledWith(expect.stringContaining("Password login")),
  );
});

test("the default Google challenge remains anonymous while custom authenticated loaders are supported", async () => {
  vi.mocked(apiFetch).mockResolvedValue({ enabled: false });
  const view = render(<GoogleSignIn onCredential={vi.fn()} onError={vi.fn()} />);
  await waitFor(() =>
    expect(apiFetch).toHaveBeenCalledWith(
      "/api/v1/auth/google/challenge",
      {},
      { skipAuth: true },
    ),
  );
  view.unmount();
  vi.mocked(apiFetch).mockClear();
  const loader = vi.fn().mockResolvedValue({ enabled: false });
  render(
    <GoogleSignIn
      onCredential={vi.fn()}
      onError={vi.fn()}
      challengeLoader={loader}
      showUnavailableMessage
      unavailableMessage="Google confirmation is unavailable; your account has not changed."
    />,
  );
  expect(await screen.findByRole("status")).toHaveTextContent(
    "your account has not changed",
  );
  expect(loader).toHaveBeenCalledOnce();
  expect(apiFetch).not.toHaveBeenCalled();
});

test("ignores duplicate Google callbacks and callbacks from an unmounted component", async () => {
  const initialize = installSdk();
  const loader = vi
    .fn()
    .mockResolvedValue({ enabled: true, client_id: "client", nonce: "fresh-nonce" });
  let resolve!: () => void;
  const onCredential = vi.fn(
    () =>
      new Promise<void>((done) => {
        resolve = done;
      }),
  );
  const onError = vi.fn();
  const view = render(
    <GoogleSignIn
      onCredential={onCredential}
      onError={onError}
      challengeLoader={loader}
    />,
  );
  const callback = await readySdk(initialize);
  act(() => {
    callback({ credential: "valid-proof" });
    callback({ credential: "duplicate-proof" });
  });
  expect(onCredential).toHaveBeenCalledOnce();
  view.unmount();
  await act(async () => {
    resolve();
    callback({ credential: "abandoned-proof" });
  });
  expect(onCredential).toHaveBeenCalledOnce();
  expect(onError).not.toHaveBeenCalled();
  expect(loader).toHaveBeenCalledOnce();
});

test("rejects an old popup callback after the Google challenge is replaced", async () => {
  const initialize = installSdk();
  const oldLoader = vi
    .fn()
    .mockResolvedValue({ enabled: true, client_id: "client", nonce: "old-nonce" });
  const newLoader = vi
    .fn()
    .mockResolvedValue({ enabled: true, client_id: "client", nonce: "new-nonce" });
  const onCredential = vi.fn().mockResolvedValue(undefined);
  const onError = vi.fn();
  const view = render(
    <GoogleSignIn
      onCredential={onCredential}
      onError={onError}
      challengeLoader={oldLoader}
    />,
  );
  const oldCallback = await readySdk(initialize);
  view.rerender(
    <GoogleSignIn
      onCredential={onCredential}
      onError={onError}
      challengeLoader={newLoader}
    />,
  );
  await waitFor(() =>
    expect(initialize).toHaveBeenLastCalledWith(
      expect.objectContaining({ nonce: "new-nonce", auto_select: false }),
    ),
  );
  await act(async () => {
    oldCallback({ credential: "stale-proof" });
  });
  expect(onCredential).not.toHaveBeenCalled();
  await act(async () => {
    initialize.mock.calls.at(-1)![0].callback({ credential: "current-proof" });
  });
  expect(onCredential).toHaveBeenCalledWith("current-proof");
});

test("retries a failed authenticated challenge without substituting password-login advice", async () => {
  const loader = vi
    .fn()
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValue({ enabled: false });
  const onError = vi.fn();
  render(
    <GoogleSignIn
      onCredential={vi.fn()}
      onError={onError}
      challengeLoader={loader}
      failureMessage="Retry Google verification; your account has not changed."
    />,
  );
  const retry = await screen.findByRole("button", { name: "Retry Google connection" });
  expect(onError).toHaveBeenCalledWith(
    "Retry Google verification; your account has not changed.",
  );
  fireEvent.click(retry);
  await waitFor(() => expect(loader).toHaveBeenCalledTimes(2));
  await waitFor(() =>
    expect(
      screen.queryByRole("button", { name: "Retry Google connection" }),
    ).not.toBeInTheDocument(),
  );
});
