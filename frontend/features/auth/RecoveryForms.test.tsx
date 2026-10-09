import { StrictMode } from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { forgotPassword, resetPassword, verifyEmail } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/errors";
import ForgotPasswordForm from "./ForgotPasswordForm";
import ResetPasswordForm from "./ResetPasswordForm";
import VerifyEmailForm from "./VerifyEmailForm";

const { clearCache } = vi.hoisted(() => ({ clearCache: vi.fn() }));
vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ clear: clearCache }),
}));
vi.mock("@/lib/api/auth", () => ({
  forgotPassword: vi.fn(),
  resetPassword: vi.fn(),
  verifyEmail: vi.fn(),
}));

function apiError(status: number) {
  return new ApiError(status, {
    error: {
      code: "RECOVERY_ERROR",
      message: "Safe backend message",
      request_id: "test",
    },
  });
}

async function passwords(password = "NewPassword123", repeat = password) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("New password", { exact: true }), password);
  await user.type(screen.getByLabelText("Repeat new password"), repeat);
  return user;
}

beforeEach(() => {
  vi.resetAllMocks();
  window.history.replaceState({}, "", "/");
  window.localStorage.clear();
  window.sessionStorage.clear();
  vi.mocked(forgotPassword).mockResolvedValue({
    message: "If this email has a password account, a reset code will be sent.",
  });
  vi.mocked(resetPassword).mockResolvedValue({ message: "Password reset." });
  vi.mocked(verifyEmail).mockResolvedValue({ message: "Email verified." });
});

describe("forgot password", () => {
  it("validates email before requesting a code and uses a neutral success message", async () => {
    const user = userEvent.setup();
    render(<ForgotPasswordForm />);
    await user.click(screen.getByRole("button", { name: "Request reset code" }));
    expect(await screen.findByText("Enter a valid email")).toBeVisible();
    expect(forgotPassword).not.toHaveBeenCalled();
    await user.type(screen.getByLabelText("Email"), "writer@example.com");
    await user.click(screen.getByRole("button", { name: "Request reset code" }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "If this email has a password account",
    );
    expect(forgotPassword).toHaveBeenCalledWith("writer@example.com");
    expect(screen.getByRole("link", { name: "login page" })).toHaveAttribute(
      "href",
      "/login",
    );
  });

  it("shows a delivery outage honestly and allows retry", async () => {
    vi.mocked(forgotPassword).mockRejectedValueOnce(apiError(503));
    const user = userEvent.setup();
    render(<ForgotPasswordForm />);
    await user.type(screen.getByLabelText("Email"), "writer@example.com");
    await user.click(screen.getByRole("button", { name: "Request reset code" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Email delivery is unavailable",
    );
    await user.click(screen.getByRole("button", { name: "Request reset code" }));
    expect(await screen.findByRole("status")).toHaveTextContent("If this email");
  });
});

describe("reset password", () => {
  it("ignores query tokens and requires a pasted code without a fragment", async () => {
    window.history.replaceState({}, "", "/reset-password?token=query-secret");
    render(
      <StrictMode>
        <ResetPasswordForm />
      </StrictMode>,
    );
    expect(screen.getByLabelText("Reset code")).toBeVisible();
    expect(window.location.search).toBe("");
    const user = await passwords();
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(await screen.findByText("Paste the reset code from your email")).toBeVisible();
    expect(resetPassword).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Reset code")).toHaveFocus();
  });

  it("requires a strong password and matching confirmation for manual recovery", async () => {
    render(<ResetPasswordForm />);
    const user = await passwords("password", "different");
    await user.type(screen.getByLabelText("Reset code"), "opaque-code");
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(await screen.findByText("Include a digit")).toBeVisible();
    expect(screen.getByText("Passwords must match")).toBeVisible();
    expect(resetPassword).not.toHaveBeenCalled();
  });

  it("consumes a fragment once through StrictMode and rerenders, then returns to login", async () => {
    const secret = "opaque_fragment_code";
    window.history.replaceState({}, "", `/reset-password#token=${secret}`);
    const view = render(
      <StrictMode>
        <ResetPasswordForm />
      </StrictMode>,
    );
    expect(window.location.hash).toBe("");
    expect(screen.queryByLabelText("Reset code")).not.toBeInTheDocument();
    view.rerender(
      <StrictMode>
        <ResetPasswordForm />
      </StrictMode>,
    );
    const user = await passwords();
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Sign in again");
    expect(resetPassword).toHaveBeenCalledExactlyOnceWith(secret, "NewPassword123");
    expect(clearCache).toHaveBeenCalledOnce();
    expect(screen.getByRole("link", { name: "Go to login" })).toHaveAttribute(
      "href",
      "/login",
    );
    expect(view.container.innerHTML).not.toContain(secret);
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
  });

  it("keeps a fragment in memory for retry after a network error", async () => {
    vi.mocked(resetPassword).mockRejectedValueOnce(new Error("offline"));
    window.history.replaceState({}, "", "/reset-password#token=retry-code");
    render(<ResetPasswordForm />);
    const user = await passwords();
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Check your connection");
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "password has been reset",
    );
    expect(resetPassword).toHaveBeenNthCalledWith(2, "retry-code", "NewPassword123");
  });

  it("discards an invalid fragment and accepts a fresh pasted code", async () => {
    vi.mocked(resetPassword).mockRejectedValueOnce(apiError(400));
    window.history.replaceState({}, "", "/reset-password#token=expired-code");
    render(<ResetPasswordForm />);
    const user = await passwords();
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "invalid, expired, or already used",
    );
    await user.type(screen.getByLabelText("Reset code"), "fresh-code");
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    await screen.findByRole("status");
    expect(resetPassword).toHaveBeenNthCalledWith(2, "fresh-code", "NewPassword123");
  });

  it("disables reset while the request is pending", async () => {
    let resolve!: (result: { message: string }) => void;
    vi.mocked(resetPassword).mockImplementation(
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    );
    window.history.replaceState({}, "", "/reset-password#token=pending-code");
    render(<ResetPasswordForm />);
    const user = await passwords();
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(screen.getByRole("button", { name: "Resetting password…" })).toBeDisabled();
    await act(async () => resolve({ message: "Password reset." }));
    expect(await screen.findByRole("status")).toHaveTextContent("Sign in again");
  });
});

describe("verify email", () => {
  it("supports manual code entry and validation without automatic submission", async () => {
    const user = userEvent.setup();
    render(<VerifyEmailForm />);
    expect(verifyEmail).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Verify email" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Paste the full verification code",
    );
    await user.type(screen.getByLabelText("Verification code"), "  copied-code  ");
    await user.click(screen.getByRole("button", { name: "Verify email" }));
    expect(await screen.findByRole("status")).toHaveTextContent("email is verified");
    expect(verifyEmail).toHaveBeenCalledExactlyOnceWith("copied-code");
  });

  it("requires an explicit click for fragment verification under StrictMode", async () => {
    window.history.replaceState({}, "", "/verify-email#token=verify-fragment");
    const user = userEvent.setup();
    render(
      <StrictMode>
        <VerifyEmailForm />
      </StrictMode>,
    );
    expect(window.location.hash).toBe("");
    expect(verifyEmail).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Verify email" }));
    await screen.findByRole("status");
    expect(verifyEmail).toHaveBeenCalledExactlyOnceWith("verify-fragment");
    expect(screen.getByRole("link", { name: "Go to account" })).toHaveAttribute(
      "href",
      "/account",
    );
  });

  it("retains the code on temporary failure and supports retry", async () => {
    vi.mocked(verifyEmail).mockRejectedValueOnce(apiError(429));
    window.history.replaceState({}, "", "/verify-email#token=retry-verify");
    const user = userEvent.setup();
    render(<VerifyEmailForm />);
    await user.click(screen.getByRole("button", { name: "Verify email" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Wait a few minutes");
    await user.click(screen.getByRole("button", { name: "Verify email" }));
    await waitFor(() => expect(verifyEmail).toHaveBeenCalledTimes(2));
    expect(verifyEmail).toHaveBeenLastCalledWith("retry-verify");
  });

  it("allows a replacement code after an expired verification link", async () => {
    vi.mocked(verifyEmail).mockRejectedValueOnce(apiError(410));
    window.history.replaceState({}, "", "/verify-email#token=expired-verify");
    const user = userEvent.setup();
    render(<VerifyEmailForm />);
    await user.click(screen.getByRole("button", { name: "Verify email" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "invalid, expired, or already used",
    );
    await user.type(screen.getByLabelText("Verification code"), "replacement-code");
    await user.click(screen.getByRole("button", { name: "Verify email" }));
    await screen.findByRole("status");
    expect(verifyEmail).toHaveBeenLastCalledWith("replacement-code");
  });
});
