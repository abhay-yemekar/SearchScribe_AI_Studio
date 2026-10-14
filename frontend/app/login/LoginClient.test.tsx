import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LoginClient from "./LoginClient";

const mocks = vi.hoisted(() => ({
  session: { token: null as string | null, bootstrapping: true },
  push: vi.fn(), replace: vi.fn(), login: vi.fn(),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push, replace: mocks.replace }),
}));
vi.mock("@/features/auth/useSession", () => ({ useSession: () => mocks.session }));
vi.mock("@/lib/api/auth", () => ({
  login: mocks.login, signup: vi.fn(), googleLogin: vi.fn(),
}));
vi.mock("@/features/auth/GoogleSignIn", () => ({
  default: () => <button>Google identity control</button>,
}));

describe("login during slow session restoration", () => {
  beforeEach(() => {
    mocks.session = { token: null, bootstrapping: true };
    mocks.login.mockResolvedValue({});
    vi.clearAllMocks();
  });

  it("shows an editable form immediately, then preserves input and unlocks sign-in", async () => {
    const view = render(<LoginClient initialMode="login" />);
    expect(screen.getByLabelText("Email")).toBeVisible();
    expect(screen.queryByText("Loading SearchScribe…")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Checking your session");
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "reader@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "correct-horse-1" } });
    expect(screen.getByRole("button", { name: "Login" })).toBeDisabled();
    expect(screen.queryByText("Google identity control")).not.toBeInTheDocument();
    expect(mocks.login).not.toHaveBeenCalled();
    mocks.session = { token: null, bootstrapping: false };
    view.rerender(<LoginClient initialMode="login" />);
    expect(screen.getByLabelText("Email")).toHaveValue("reader@example.com");
    expect(screen.getByRole("button", { name: "Login" })).toBeEnabled();
    expect(screen.getByText("Google identity control")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Login" }));
    await waitFor(() => expect(mocks.login).toHaveBeenCalledOnce());
    expect(mocks.push).toHaveBeenCalledWith("/dashboard");
  });

  it("redirects a restored session without creating a second login", async () => {
    const view = render(<LoginClient initialMode="signup" />);
    expect(screen.getByLabelText("Name")).toBeVisible();
    mocks.session = { token: "restored-token", bootstrapping: false };
    view.rerender(<LoginClient initialMode="signup" />);
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/dashboard"));
    expect(screen.getByText("Opening your workspace…")).toBeVisible();
    expect(mocks.login).not.toHaveBeenCalled();
  });
});
