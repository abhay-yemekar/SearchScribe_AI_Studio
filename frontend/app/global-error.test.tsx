import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

const reportError = vi.hoisted(() => vi.fn());
vi.mock("@/lib/sentry", () => ({ reportError }));

import GlobalError from "./global-error";

describe("GlobalError", () => {
  it("reports the crash and offers a retry and a way home", async () => {
    const error = Object.assign(new Error("layout crashed"), { digest: "abc" });
    const retry = vi.fn();
    // Rendered inside the test document; the real one replaces <html>.
    render(<GlobalError error={error} retry={retry} />, {
      container: document.documentElement,
    });

    expect(reportError).toHaveBeenCalledWith(error);
    expect(screen.getByRole("heading", { name: "Something went wrong" })).toBeVisible();
    expect(screen.queryByText(/layout crashed/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to the homepage" })).toHaveAttribute(
      "href",
      "/",
    );
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalled();
  });
});
