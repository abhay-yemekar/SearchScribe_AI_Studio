import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import AccountPage from "./page";
import { useSession } from "@/features/auth/useSession";
import { apiFetch } from "@/lib/api/client";
import { fetchCurrentUser, requestEmailVerification } from "@/lib/api/auth";

const { router } = vi.hoisted(() => ({ router: { replace: vi.fn() } }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("@/features/auth/useSession", () => ({ useSession: vi.fn() }));
vi.mock("@/features/auth/GoogleSignIn", () => ({ default: () => null }));
vi.mock("@/lib/api/client", () => ({ apiFetch: vi.fn() }));
vi.mock("@/lib/api/auth", () => ({
  fetchCurrentUser: vi.fn(),
  requestEmailVerification: vi.fn(),
  linkGoogle: vi.fn(),
}));

const user = {
  id: 1,
  name: "Writer",
  email: "writer@example.com",
  created_at: "2026-10-09",
  email_verified: false,
};
const setUser = vi.fn();

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
    message: "If email delivery is available, a verification code will be sent.",
  });
  vi.mocked(fetchCurrentUser).mockResolvedValue({ ...user, email_verified: true });
});

it("shows unverified email and resend feedback while preserving linked Google status", async () => {
  const interaction = userEvent.setup();
  render(<AccountPage />);
  expect(screen.getByText("Email not verified")).toBeVisible();
  await screen.findByText("Google is linked to your account.");
  await interaction.click(screen.getByRole("button", { name: "Send verification code" }));
  expect(
    await screen.findByText(
      "If email delivery is available, a verification code will be sent.",
    ),
  ).toBeVisible();
  expect(screen.getByRole("button", { name: "Resend verification code" })).toBeEnabled();
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
    screen.queryByRole("button", { name: "Send verification code" }),
  ).not.toBeInTheDocument();
  await screen.findByText("Google is linked to your account.");
});

it("allows retry after an email request fails", async () => {
  vi.mocked(requestEmailVerification).mockRejectedValueOnce(new Error("offline"));
  const interaction = userEvent.setup();
  render(<AccountPage />);
  await interaction.click(screen.getByRole("button", { name: "Send verification code" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Check your connection");
  await interaction.click(screen.getByRole("button", { name: "Send verification code" }));
  await screen.findByText(
    "If email delivery is available, a verification code will be sent.",
  );
  expect(requestEmailVerification).toHaveBeenCalledTimes(2);
});
