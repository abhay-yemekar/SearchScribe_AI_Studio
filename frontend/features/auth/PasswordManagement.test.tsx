import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import PasswordManagement from "./PasswordManagement";
import { addPassword, changePassword, passwordAddChallenge } from "@/lib/api/auth";
import { clearAccessToken, getSnapshot, setAccessToken } from "@/lib/auth/token-store";
import { ApiError } from "@/lib/api/errors";

const { google } = vi.hoisted(() => ({
  google: {
    props: null as null | {
      challengeLoader: () => Promise<unknown>;
      onCredential: (credential: string) => Promise<void>;
    },
  },
}));
vi.mock("@/lib/api/auth", () => ({
  addPassword: vi.fn(),
  changePassword: vi.fn(),
  passwordAddChallenge: vi.fn(),
}));
vi.mock("./GoogleSignIn", () => ({
  default: (props: NonNullable<typeof google.props>) => {
    google.props = props;
    return (
      <button type="button" onClick={() => void props.onCredential("fresh-google-proof")}>
        Confirm Google account
      </button>
    );
  },
}));

beforeEach(() => {
  vi.resetAllMocks();
  google.props = null;
  clearAccessToken();
  setAccessToken("existing-session", 900);
  vi.mocked(addPassword).mockResolvedValue(undefined);
  vi.mocked(changePassword).mockResolvedValue(undefined);
});

function mount(hasPassword = true) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(["articles"], [{ id: 1, title: "Private draft" }]);
  const onComplete = vi.fn();
  const view = render(
    <QueryClientProvider client={queryClient}>
      <PasswordManagement hasPassword={hasPassword} onComplete={onComplete} />
    </QueryClientProvider>,
  );
  return { ...view, queryClient, onComplete, interaction: userEvent.setup() };
}

async function fillNew(
  interaction: ReturnType<typeof userEvent.setup>,
  confirmation = "NewPassword123",
) {
  await interaction.type(screen.getByLabelText("New password"), "NewPassword123");
  await interaction.type(screen.getByLabelText("Confirm new password"), confirmation);
}

it("validates password confirmation before allowing fresh Google authorization", async () => {
  const { interaction } = mount(false);
  expect(screen.getByText(/it has no password yet/)).toBeVisible();
  expect(screen.queryByLabelText("Current password")).not.toBeInTheDocument();
  await fillNew(interaction, "Different123");
  await interaction.click(screen.getByRole("button", { name: "Continue with Google" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Passwords must match");
  expect(google.props).toBeNull();
  expect(addPassword).not.toHaveBeenCalled();
});

it("adds a password with fresh Google proof, clears private state, and keeps Google available", async () => {
  const { interaction, queryClient, onComplete } = mount(false);
  await fillNew(interaction);
  await interaction.click(screen.getByRole("button", { name: "Continue with Google" }));
  expect(google.props?.challengeLoader).toBe(passwordAddChallenge);
  await interaction.click(
    await screen.findByRole("button", { name: "Confirm Google account" }),
  );
  await waitFor(() =>
    expect(addPassword).toHaveBeenCalledWith("fresh-google-proof", "NewPassword123"),
  );
  expect(onComplete).toHaveBeenCalledWith(
    expect.stringContaining("Google sign-in is still available"),
  );
  expect(getSnapshot()).toBeNull();
  expect(queryClient.getQueryData(["articles"])).toBeUndefined();
  expect(screen.getByLabelText("New password")).toHaveValue("");
  expect(screen.getByLabelText("Confirm new password")).toHaveValue("");
});

it("invalidates an abandoned Google step when the chosen password is edited", async () => {
  const { interaction } = mount(false);
  await fillNew(interaction);
  await interaction.click(screen.getByRole("button", { name: "Continue with Google" }));
  const oldCallback = google.props!.onCredential;
  await interaction.type(screen.getByLabelText("New password"), "4");
  expect(
    screen.queryByRole("button", { name: "Confirm Google account" }),
  ).not.toBeInTheDocument();
  await act(async () => {
    await oldCallback("abandoned-google-proof");
  });
  expect(addPassword).not.toHaveBeenCalled();
});

it("changes a password and only reveals passwords entered in the form", async () => {
  const { interaction, queryClient, onComplete } = mount();
  expect(screen.getByText(/current password cannot be viewed/)).toBeVisible();
  await interaction.type(screen.getByLabelText("Current password"), "OldPassword123");
  await fillNew(interaction);
  await interaction.click(screen.getByRole("button", { name: "Show entered passwords" }));
  expect(screen.getByLabelText("Current password")).toHaveAttribute("type", "text");
  expect(screen.getByRole("button", { name: "Hide entered passwords" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await interaction.click(screen.getByRole("button", { name: "Change password" }));
  expect(changePassword).toHaveBeenCalledWith("OldPassword123", "NewPassword123");
  expect(onComplete).toHaveBeenCalledWith(
    "Password updated. Sign in again with your new password.",
  );
  expect(getSnapshot()).toBeNull();
  expect(queryClient.getQueryData(["articles"])).toBeUndefined();
});

it("keeps the current session and allows correction after a wrong current password", async () => {
  vi.mocked(changePassword).mockRejectedValueOnce(
    new ApiError(401, {
      error: {
        code: "PASSWORD_CURRENT_INVALID",
        message: "Wrong password",
        request_id: "test",
      },
    }),
  );
  const { interaction, onComplete } = mount();
  await interaction.type(screen.getByLabelText("Current password"), "WrongPassword123");
  await fillNew(interaction);
  await interaction.click(screen.getByRole("button", { name: "Change password" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "current password was not accepted",
  );
  expect(getSnapshot()).toBe("existing-session");
  expect(onComplete).not.toHaveBeenCalled();
  await interaction.clear(screen.getByLabelText("Current password"));
  await interaction.type(screen.getByLabelText("Current password"), "CorrectPassword123");
  await interaction.click(screen.getByRole("button", { name: "Change password" }));
  expect(changePassword).toHaveBeenLastCalledWith("CorrectPassword123", "NewPassword123");
  expect(onComplete).toHaveBeenCalledOnce();
});

it("blocks duplicate mutations and clears secrets even if a successful request finishes after unmount", async () => {
  let resolve!: () => void;
  vi.mocked(changePassword).mockImplementationOnce(
    () =>
      new Promise<void>((done) => {
        resolve = done;
      }),
  );
  const { interaction, queryClient, onComplete, unmount } = mount();
  await interaction.type(screen.getByLabelText("Current password"), "OldPassword123");
  await fillNew(interaction);
  await interaction.dblClick(screen.getByRole("button", { name: "Change password" }));
  expect(changePassword).toHaveBeenCalledOnce();
  expect(screen.getByLabelText("New password")).toBeDisabled();
  unmount();
  await act(async () => {
    resolve();
  });
  expect(getSnapshot()).toBeNull();
  expect(queryClient.getQueryData(["articles"])).toBeUndefined();
  expect(onComplete).not.toHaveBeenCalled();
});

it("clears the local session and private cache when HTTP success has an unreadable response body", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/auth")>("@/lib/api/auth");
  vi.mocked(changePassword).mockImplementationOnce(actual.changePassword);
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response("truncated-json", { status: 200 })),
  );
  const { interaction, queryClient, onComplete } = mount();
  await interaction.type(screen.getByLabelText("Current password"), "OldPassword123");
  await fillNew(interaction);
  await interaction.click(screen.getByRole("button", { name: "Change password" }));
  await waitFor(() => expect(onComplete).toHaveBeenCalledOnce());
  expect(getSnapshot()).toBeNull();
  expect(queryClient.getQueryData(["articles"])).toBeUndefined();
  vi.unstubAllGlobals();
});

it("offers a sign-in route for an expired session without pretending a password changed", async () => {
  vi.mocked(changePassword).mockRejectedValueOnce(
    new ApiError(401, {
      error: {
        code: "AUTHENTICATION_REQUIRED",
        message: "Session expired",
        request_id: "test",
      },
    }),
  );
  const { interaction, onComplete } = mount();
  await interaction.type(screen.getByLabelText("Current password"), "OldPassword123");
  await fillNew(interaction);
  await interaction.click(screen.getByRole("button", { name: "Change password" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("session expired");
  expect(screen.getByRole("link", { name: "Sign in again" })).toHaveAttribute(
    "href",
    "/login",
  );
  expect(onComplete).not.toHaveBeenCalled();
});
