import { act, render, waitFor } from "@testing-library/react";
import { vi, test, expect } from "vitest";
import GoogleSignIn from "./GoogleSignIn";

vi.mock("@/lib/api/client", () => ({ apiFetch: vi.fn() }));
vi.mock("next/script", () => ({ default: () => null }));
import { apiFetch } from "@/lib/api/client";

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
