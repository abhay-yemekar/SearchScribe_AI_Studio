import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

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
  it("saves trimmed editable metadata without mutating the loaded snapshot", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    render(<SeoPanel seo={seo} saving={false} onSave={onSave} />);

    await user.click(screen.getByRole("button", { name: /edit seo/i }));
    const title = screen.getByLabelText(/seo title/i);
    await user.clear(title);
    await user.type(title, "A better Kerala guide");
    const keywords = screen.getByLabelText(/keywords/i);
    await user.clear(keywords);
    await user.type(keywords, " kerala, backwaters ");
    const canonical = screen.getByLabelText(/canonical url/i);
    await user.type(canonical, "https://example.com/kerala ");
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
    await user.type(screen.getByLabelText(/seo title/i), "Discard this");
    await user.click(screen.getByRole("button", { name: /cancel/i }));

    expect(screen.getAllByText("Kerala travel guide")).toHaveLength(2);
  });
});
