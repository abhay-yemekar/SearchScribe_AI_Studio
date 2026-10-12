import { render as renderView, screen, waitFor } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import AccountPage from "./page";
import { useSession } from "@/features/auth/useSession";
import { apiFetch } from "@/lib/api/client";
import {
  changePassword,
  fetchCurrentUser,
  requestEmailVerification,
} from "@/lib/api/auth";

const { router } = vi.hoisted(() => ({ router: { replace: vi.fn() } }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("@/features/auth/useSession", () => ({ useSession: vi.fn() }));
vi.mock("@/features/auth/GoogleSignIn", () => ({ default: () => null }));
vi.mock("@/lib/api/client", () => ({ apiFetch: vi.fn() }));
vi.mock("@/lib/api/auth", () => ({
  fetchCurrentUser: vi.fn(),
  requestEmailVerification: vi.fn(),
  linkGoogle: vi.fn(),
  addPassword: vi.fn(),
  changePassword: vi.fn(),
  passwordAddChallenge: vi.fn(),
}));

const user = {
  id: 1,
  name: "Writer",
  email: "writer@example.com",
  created_at: "2026-10-09",
  email_verified: false,
};
const setUser = vi.fn();

function render(element: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderView(element, {
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  });
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(useSession).mockReturnValue({
    token: "signed-in",
    user,
    bootstrapping: false,
    setUser,
    logout: vi.fn(),
  });
  vi.mocked(apiFetch).mockResolvedValue({ password: true, google: true });
  vi.mocked(requestEmailVerification).mockResolvedValue({
    message: "If email delivery is available, verification instructions will be sent.",
  });
  vi.mocked(fetchCurrentUser).mockResolvedValue({ ...user, email_verified: true });
});

it("shows unverified email and resend feedback while preserving linked Google status", async () => {
  const interaction = userEvent.setup();
  render(<AccountPage />);
  expect(screen.getByText("Email not verified")).toBeVisible();
  await screen.findByText("Google is linked to your account.");
  await interaction.click(
    screen.getByRole("button", { name: "Send verification email" }),
  );
  expect(
    await screen.findByText(
      "If email delivery is available, verification instructions will be sent.",
    ),
  ).toBeVisible();
  expect(screen.getByRole("button", { name: "Resend verification email" })).toBeEnabled();
  await interaction.click(
    screen.getByRole("button", { name: "Refresh verification status" }),
  );
  await waitFor(() =>
    expect(setUser).toHaveBeenCalledWith({ ...user, email_verified: true }),
  );
});

it("hides resend once email is verified", async () => {
  vi.mocked(useSession).mockReturnValue({
    token: "signed-in",
    user: { ...user, email_verified: true },
    bootstrapping: false,
    setUser,
    logout: vi.fn(),
  });
  render(<AccountPage />);
  expect(screen.getByText("Email verified")).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Send verification email" }),
  ).not.toBeInTheDocument();
  await screen.findByText("Google is linked to your account.");
});

it("allows retry after an email request fails", async () => {
  vi.mocked(requestEmailVerification).mockRejectedValueOnce(new Error("offline"));
  const interaction = userEvent.setup();
  render(<AccountPage />);
  await interaction.click(
    screen.getByRole("button", { name: "Send verification email" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("Check your connection");
  await interaction.click(
    screen.getByRole("button", { name: "Send verification email" }),
  );
  await screen.findByText(
    "If email delivery is available, verification instructions will be sent.",
  );
  expect(requestEmailVerification).toHaveBeenCalledTimes(2);
});

it("does not assume Google-only sign-in while connections load or fail", async () => {
  vi.mocked(apiFetch).mockRejectedValueOnce(new Error("offline"));
  const interaction = userEvent.setup();
  render(<AccountPage />);
  expect(screen.getByText("Loading sign-in methods…")).toBeVisible();
  expect(
    screen.queryByRole("region", { name: "Add a password" }),
  ).not.toBeInTheDocument();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Could not load account connections",
  );
  expect(screen.queryByLabelText("New password")).not.toBeInTheDocument();
  await interaction.click(screen.getByRole("button", { name: "Retry sign-in methods" }));
  expect(await screen.findByRole("region", { name: "Change password" })).toBeVisible();
});

it("keeps password-change confirmation visible after the revoked session disappears", async () => {
  vi.mocked(changePassword).mockResolvedValue(undefined);
  const interaction = userEvent.setup();
  const view = render(<AccountPage />);
  await screen.findByRole("region", { name: "Change password" });
  await interaction.type(screen.getByLabelText("Current password"), "OldPassword123");
  await interaction.type(screen.getByLabelText("New password"), "NewPassword123");
  await interaction.type(screen.getByLabelText("Confirm new password"), "NewPassword123");
  await interaction.click(screen.getByRole("button", { name: "Change password" }));
  expect(
    await screen.findByText("Password updated. Sign in again with your new password."),
  ).toBeVisible();
  vi.mocked(useSession).mockReturnValue({
    token: null,
    user: null,
    bootstrapping: false,
    setUser,
    logout: vi.fn(),
  });
  view.rerender(<AccountPage />);
  expect(screen.getByRole("link", { name: "Go to login" })).toHaveAttribute(
    "href",
    "/login",
  );
  expect(screen.getByRole("link", { name: "Back to website" })).toHaveAttribute(
    "href",
    "/",
  );
  expect(screen.queryByLabelText("New password")).not.toBeInTheDocument();
  expect(router.replace).not.toHaveBeenCalled();
  expect(setUser).toHaveBeenCalledWith(null);
});
