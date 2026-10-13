import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SeoPanel from "./SeoPanel";

const seo = {
  title: "Kerala travel guide",
  description: "Plan a memorable Kerala trip.",
  keywords: ["kerala", "travel"],
  og_title: null,
  og_description: null,
  canonical_url: null,
  robots: "index, follow" as const,
};

describe("SeoPanel", () => {
  beforeEach(() => {
    Object.defineProperties(HTMLDialogElement.prototype, {
      showModal: {
        configurable: true,
        value: vi.fn(function (this: HTMLDialogElement) {
          this.setAttribute("open", "");
        }),
      },
      close: {
        configurable: true,
        value: vi.fn(function (this: HTMLDialogElement) {
          this.removeAttribute("open");
        }),
      },
    });
  });
  it("saves trimmed editable metadata without mutating the loaded snapshot", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    render(<SeoPanel seo={seo} saving={false} onSave={onSave} />);

    await user.click(screen.getByRole("button", { name: /edit seo/i }));
    const title = screen.getByLabelText(/seo title/i);
    await user.clear(title);
    await user.paste("A better Kerala guide");
    const keywords = screen.getByLabelText(/keywords/i);
    await user.clear(keywords);
    await user.paste(" kerala, backwaters ");
    const canonical = screen.getByLabelText(/canonical url/i);
    await user.click(canonical);
    await user.paste("https://example.com/kerala ");
    await user.click(screen.getByRole("button", { name: /save version/i }));

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "A better Kerala guide",
        keywords: ["kerala", "backwaters"],
        canonical_url: "https://example.com/kerala",
      }),
    );
    expect(seo.title).toBe("Kerala travel guide");
  });

  it("cancels edits and restores the loaded snapshot", async () => {
    const user = userEvent.setup();
    render(<SeoPanel seo={seo} saving={false} onSave={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /edit seo/i }));
    await user.clear(screen.getByLabelText(/seo title/i));
    await user.paste("Discard this");
    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(
      screen.getByRole("dialog", { name: "Discard unsaved changes?" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Discard changes" }));
    await screen.findByRole("button", { name: "Edit SEO" });
    expect(screen.getAllByText("Kerala travel guide")).toHaveLength(2);
  });

  it("retains SEO edits and original snapshot when a failed save races a query refresh", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockRejectedValue(new Error("Version conflict"));
    const view = render(<SeoPanel seo={seo} saving={false} onSave={onSave} />);
    await user.click(screen.getByRole("button", { name: /edit seo/i }));
    await user.click(screen.getByLabelText(/seo title/i));
    await user.paste(" changed");
    view.rerender(
      <SeoPanel
        seo={{ ...seo, description: "New server SEO" }}
        saving={false}
        onSave={onSave}
      />,
    );
    await user.click(screen.getByRole("button", { name: /save version/i }));
    expect(screen.getByLabelText(/seo title/i)).toHaveValue(
      "Kerala travel guide changed",
    );
    expect(screen.getByLabelText(/meta description/i)).toHaveValue(seo.description);
  });
});
