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

async function openLegacyCode() {
  const user = userEvent.setup();
  const disclosure = screen.getByRole("button", {
    name: "Have a code from an older email?",
  });
  expect(disclosure).toHaveAttribute("aria-expanded", "false");
  await user.click(disclosure);
  expect(disclosure).toHaveAttribute("aria-expanded", "true");
  return user;
}

const resetToken = "reset_link_token_0123456789";
const verifyToken = "verify_link_token_0123456789";
const legacyToken = "legacy_email_code_0123456789";

function navigateFragment(path: string, fragment: string) {
  const oldURL = window.location.href;
  act(() => {
    window.history.replaceState({}, "", `${path}#${fragment}`);
    window.dispatchEvent(
      new HashChangeEvent("hashchange", { oldURL, newURL: window.location.href }),
    );
  });
}

beforeEach(() => {
  vi.resetAllMocks();
  window.history.replaceState({}, "", "/");
  window.localStorage.clear();
  window.sessionStorage.clear();
  vi.mocked(forgotPassword).mockResolvedValue({
    message: "If this email has a password account, reset instructions will be sent.",
  });
  vi.mocked(resetPassword).mockResolvedValue({ message: "Password reset." });
  vi.mocked(verifyEmail).mockResolvedValue({ message: "Email verified." });
});

describe("forgot password", () => {
  it("validates email before requesting instructions and uses a neutral success message", async () => {
    const user = userEvent.setup();
    render(<ForgotPasswordForm />);
    await user.click(screen.getByRole("button", { name: "Request reset email" }));
    expect(await screen.findByText("Enter a valid email")).toBeVisible();
    expect(forgotPassword).not.toHaveBeenCalled();
    await user.type(screen.getByLabelText("Email"), "writer@example.com");
    await user.click(screen.getByRole("button", { name: "Request reset email" }));
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
    await user.click(screen.getByRole("button", { name: "Request reset email" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Email delivery is unavailable",
    );
    await user.click(screen.getByRole("button", { name: "Request reset email" }));
    expect(await screen.findByRole("status")).toHaveTextContent("If this email");
  });
});

describe("reset password", () => {
  it("ignores query tokens and keeps legacy code entry behind a disclosure", async () => {
    window.history.replaceState({}, "", "/reset-password?token=query-secret");
    render(
      <StrictMode>
        <ResetPasswordForm />
      </StrictMode>,
    );
    expect(screen.getByLabelText("Reset code")).not.toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Reset password" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Request a new reset link" }),
    ).toHaveAttribute("href", "/forgot-password");
    expect(window.location.search).toBe("");
    await openLegacyCode();
    const user = await passwords();
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(
      await screen.findByText(
        "Paste the complete code from your older email, or request a new link",
      ),
    ).toBeVisible();
    expect(resetPassword).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Reset code")).toHaveFocus();
  });

  it("requires a strong password and matching confirmation for manual recovery", async () => {
    render(<ResetPasswordForm />);
    await openLegacyCode();
    const user = await passwords("password", "different");
    await user.type(screen.getByLabelText("Reset code"), legacyToken);
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
    expect(resetPassword).not.toHaveBeenCalled();
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
    window.history.replaceState({}, "", `/reset-password#token=${resetToken}`);
    render(<ResetPasswordForm />);
    const user = await passwords();
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Check your connection");
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "password has been reset",
    );
    expect(resetPassword).toHaveBeenNthCalledWith(2, resetToken, "NewPassword123");
  });

  it("shows a terminal expired-link state instead of reopening code entry", async () => {
    vi.mocked(resetPassword).mockRejectedValueOnce(apiError(400));
    window.history.replaceState({}, "", `/reset-password#token=${resetToken}`);
    render(<ResetPasswordForm />);
    const user = await passwords();
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "invalid, expired, or already used",
    );
    expect(
      screen.getByRole("link", { name: "Request a new reset link" }),
    ).toHaveAttribute("href", "/forgot-password");
    expect(
      screen.queryByLabelText("New password", { exact: true }),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Reset code")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Have a code from an older email?" }),
    ).not.toBeInTheDocument();
    expect(resetPassword).toHaveBeenCalledOnce();
  });

  it("disables reset while the request is pending", async () => {
    let resolve!: (result: { message: string }) => void;
    vi.mocked(resetPassword).mockImplementation(
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    );
    window.history.replaceState({}, "", `/reset-password#token=${resetToken}`);
    render(<ResetPasswordForm />);
    const user = await passwords();
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(screen.getByRole("button", { name: "Resetting password…" })).toBeDisabled();
    await act(async () => resolve({ message: "Password reset." }));
    expect(await screen.findByRole("status")).toHaveTextContent("Sign in again");
  });

  it("accepts an old-email code only after the disclosure is opened", async () => {
    render(<ResetPasswordForm />);
    await openLegacyCode();
    const user = await passwords();
    await user.type(screen.getByLabelText("Reset code"), ` ${legacyToken} `);
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(await screen.findByText(/Your password has been reset/)).toBeVisible();
    expect(resetPassword).toHaveBeenCalledExactlyOnceWith(legacyToken, "NewPassword123");
  });

  it.each([
    "token=short",
    `token=${"x".repeat(201)}`,
    "token=",
    `token=${resetToken}&token=${resetToken}`,
    `token=${encodeURIComponent("x".repeat(20) + " ")}`,
    `token=${encodeURIComponent("💌".repeat(10))}`,
  ])("rejects malformed reset fragment %s without a request", (fragment) => {
    window.history.replaceState({}, "", `/reset-password#${fragment}`);
    render(
      <StrictMode>
        <ResetPasswordForm />
      </StrictMode>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("reset link is invalid");
    expect(
      screen.getByRole("link", { name: "Request a new reset link" }),
    ).toHaveAttribute("href", "/forgot-password");
    expect(
      screen.queryByLabelText("New password", { exact: true }),
    ).not.toBeInTheDocument();
    expect(resetPassword).not.toHaveBeenCalled();
    expect(window.location.hash).toBe("");
  });

  it("does not let an old reset response replace a newly opened link", async () => {
    let finishOld!: (result: { message: string }) => void;
    vi.mocked(resetPassword).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finishOld = resolve;
        }),
    );
    window.history.replaceState({}, "", `/reset-password#token=${resetToken}`);
    render(
      <StrictMode>
        <ResetPasswordForm />
      </StrictMode>,
    );
    const user = await passwords();
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    const replacement = "replacement_reset_link_0123456789";
    navigateFragment("/reset-password", `token=${replacement}`);
    expect(window.location.hash).toBe("");
    expect(screen.getByLabelText("New password", { exact: true })).toHaveValue("");
    await act(async () => finishOld({ message: "Old password reset." }));
    expect(screen.queryByText(/Your password has been reset/)).not.toBeInTheDocument();
    expect(clearCache).toHaveBeenCalledOnce();
    const newUser = await passwords("DifferentPassword456");
    await newUser.click(screen.getByRole("button", { name: "Reset password" }));
    await screen.findByText(/Your password has been reset/);
    expect(resetPassword).toHaveBeenLastCalledWith(replacement, "DifferentPassword456");
    expect(clearCache).toHaveBeenCalledTimes(2);
  });

  it("keeps a valid link available when the server rejects the new password", async () => {
    vi.mocked(resetPassword).mockRejectedValueOnce(
      new ApiError(422, {
        error: {
          code: "VALIDATION_ERROR",
          message: "Invalid input",
          request_id: "test",
          details: { fields: [{ field: "password", issue: "Password policy" }] },
        },
      }),
    );
    window.history.replaceState({}, "", `/reset-password#token=${resetToken}`);
    render(<ResetPasswordForm />);
    const user = await passwords();
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "new password was not accepted",
    );
    await user.click(screen.getByRole("button", { name: "Reset password" }));
    await screen.findByText(/Your password has been reset/);
    expect(resetPassword).toHaveBeenLastCalledWith(resetToken, "NewPassword123");
  });
});

describe("verify email", () => {
  it("supports manual code entry and validation without automatic submission", async () => {
    const user = userEvent.setup();
    render(<VerifyEmailForm />);
    expect(verifyEmail).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Verification code")).not.toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Confirm email" }),
    ).not.toBeInTheDocument();
    await openLegacyCode();
    await user.click(screen.getByRole("button", { name: "Confirm email" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Paste the complete code from your older email",
    );
    await user.type(screen.getByLabelText("Verification code"), `  ${legacyToken}  `);
    await user.click(screen.getByRole("button", { name: "Confirm email" }));
    expect(await screen.findByText(/Your email is verified/)).toBeVisible();
    expect(verifyEmail).toHaveBeenCalledExactlyOnceWith(legacyToken);
  });

  it("requires an explicit click for fragment verification under StrictMode", async () => {
    window.history.replaceState({}, "", `/verify-email#token=${verifyToken}`);
    const user = userEvent.setup();
    render(
      <StrictMode>
        <VerifyEmailForm />
      </StrictMode>,
    );
    expect(window.location.hash).toBe("");
    expect(verifyEmail).not.toHaveBeenCalled();
    expect(screen.queryByLabelText("Verification code")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirm email" }));
    await screen.findByRole("status");
    expect(verifyEmail).toHaveBeenCalledExactlyOnceWith(verifyToken);
    expect(screen.getByRole("link", { name: "Go to account" })).toHaveAttribute(
      "href",
      "/account",
    );
  });

  it("retains the code on temporary failure and supports retry", async () => {
    vi.mocked(verifyEmail).mockRejectedValueOnce(apiError(429));
    window.history.replaceState({}, "", `/verify-email#token=${verifyToken}`);
    const user = userEvent.setup();
    render(<VerifyEmailForm />);
    await user.click(screen.getByRole("button", { name: "Confirm email" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Wait a few minutes");
    await user.click(screen.getByRole("button", { name: "Confirm email" }));
    await waitFor(() => expect(verifyEmail).toHaveBeenCalledTimes(2));
    expect(verifyEmail).toHaveBeenLastCalledWith(verifyToken);
  });

  it("shows a terminal expired verification link with a request-new-link action", async () => {
    vi.mocked(verifyEmail).mockRejectedValueOnce(apiError(410));
    window.history.replaceState({}, "", `/verify-email#token=${verifyToken}`);
    const user = userEvent.setup();
    render(<VerifyEmailForm />);
    await user.click(screen.getByRole("button", { name: "Confirm email" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "invalid, expired, or already used",
    );
    expect(
      screen.getByRole("link", { name: "Request a new verification link" }),
    ).toHaveAttribute("href", "/account");
    expect(
      screen.queryByRole("button", { name: "Confirm email" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Verification code")).not.toBeInTheDocument();
    expect(verifyEmail).toHaveBeenCalledOnce();
  });

  it.each([20, 200])(
    "keeps a %s-character link token hidden until explicit confirmation",
    async (length) => {
      const token = "x".repeat(length);
      window.history.replaceState({}, "", `/verify-email#token=${token}`);
      const user = userEvent.setup();
      const view = render(
        <StrictMode>
          <VerifyEmailForm />
        </StrictMode>,
      );
      expect(verifyEmail).not.toHaveBeenCalled();
      expect(view.container.innerHTML).not.toContain(token);
      expect(window.location.hash).toBe("");
      await user.click(screen.getByRole("button", { name: "Confirm email" }));
      await screen.findByText(/Your email is verified/);
      expect(verifyEmail).toHaveBeenCalledExactlyOnceWith(token);
    },
  );

  it("allows a new legacy code after an old code has expired", async () => {
    vi.mocked(verifyEmail).mockRejectedValueOnce(apiError(400));
    render(<VerifyEmailForm />);
    const user = await openLegacyCode();
    await user.type(screen.getByLabelText("Verification code"), legacyToken);
    await user.click(screen.getByRole("button", { name: "Confirm email" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "code is invalid, expired",
    );
    await user.type(screen.getByLabelText("Verification code"), verifyToken);
    await user.click(screen.getByRole("button", { name: "Confirm email" }));
    await screen.findByText(/Your email is verified/);
    expect(verifyEmail).toHaveBeenLastCalledWith(verifyToken);
  });

  it("reads later links under StrictMode and ignores an earlier successful response", async () => {
    let finishOld!: (result: { message: string }) => void;
    vi.mocked(verifyEmail).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finishOld = resolve;
        }),
    );
    window.history.replaceState({}, "", `/verify-email#token=${verifyToken}`);
    const user = userEvent.setup();
    render(
      <StrictMode>
        <VerifyEmailForm />
      </StrictMode>,
    );
    await user.click(screen.getByRole("button", { name: "Confirm email" }));
    const replacement = "replacement_verify_link_0123456789";
    navigateFragment("/verify-email", `token=${replacement}`);
    expect(window.location.hash).toBe("");
    expect(screen.getByRole("button", { name: "Confirm email" })).toBeEnabled();
    await act(async () => finishOld({ message: "Old email verified." }));
    expect(screen.queryByText(/Your email is verified/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirm email" }));
    await screen.findByText(/Your email is verified/);
    expect(verifyEmail).toHaveBeenLastCalledWith(replacement);
  });

  it("does not let an older failure clear the new request's busy state or token", async () => {
    let rejectOld!: (error: unknown) => void;
    let finishNew!: (result: { message: string }) => void;
    vi.mocked(verifyEmail)
      .mockImplementationOnce(
        () =>
          new Promise((_resolve, reject) => {
            rejectOld = reject;
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finishNew = resolve;
          }),
      );
    window.history.replaceState({}, "", `/verify-email#token=${verifyToken}`);
    const user = userEvent.setup();
    render(<VerifyEmailForm />);
    await user.click(screen.getByRole("button", { name: "Confirm email" }));
    navigateFragment("/verify-email", `token=${resetToken}`);
    await user.click(screen.getByRole("button", { name: "Confirm email" }));
    await act(async () => rejectOld(apiError(400)));
    expect(screen.getByRole("button", { name: "Confirming email…" })).toBeDisabled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await act(async () => finishNew({ message: "New email verified." }));
    await screen.findByText(/Your email is verified/);
    expect(verifyEmail).toHaveBeenLastCalledWith(resetToken);
  });

  it("replaces the old token with a terminal state when a later fragment is malformed", () => {
    window.history.replaceState({}, "", `/verify-email#token=${verifyToken}`);
    render(
      <StrictMode>
        <VerifyEmailForm />
      </StrictMode>,
    );
    navigateFragment("/verify-email", `token=${encodeURIComponent("💌".repeat(10))}`);
    expect(window.location.hash).toBe("");
    expect(screen.getByRole("alert")).toHaveTextContent("verification link is invalid");
    expect(
      screen.queryByRole("button", { name: "Confirm email" }),
    ).not.toBeInTheDocument();
    expect(verifyEmail).not.toHaveBeenCalled();
  });

  it("leaves other page fragments alone after the recovery component unmounts", () => {
    window.history.replaceState({}, "", `/verify-email#token=${verifyToken}`);
    const view = render(
      <StrictMode>
        <VerifyEmailForm />
      </StrictMode>,
    );
    view.unmount();
    navigateFragment("/features", "section=examples");
    expect(window.location.hash).toBe("#section=examples");
    expect(verifyEmail).not.toHaveBeenCalled();
  });

  it("shows a new-link action for a server token-validation failure", async () => {
    vi.mocked(verifyEmail).mockRejectedValueOnce(apiError(422));
    window.history.replaceState({}, "", `/verify-email#token=${verifyToken}`);
    const user = userEvent.setup();
    render(<VerifyEmailForm />);
    await user.click(screen.getByRole("button", { name: "Confirm email" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "verification link is invalid",
    );
    expect(
      screen.getByRole("link", { name: "Request a new verification link" }),
    ).toHaveFocus();
  });
});
