import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { seoSchema, type Seo } from "@/lib/api/schemas";
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

  it("accepts legacy metadata and asks for review without inventing a quality status", () => {
    const legacy = seoSchema.parse(seo);
    expect(legacy.review_status).toBeUndefined();
    render(<SeoPanel seo={legacy} saving={false} onSave={vi.fn()} />);
    const status = screen.getByRole("region", { name: "SEO review status" });
    expect(within(status).getByText("Review SEO before publishing")).toBeVisible();
    expect(
      within(status).getByText(/source of this metadata is not recorded/i),
    ).toBeVisible();
  });

  it.each([
    ["generated", "AI draft — review before publishing"],
    ["edited", "Edited by you"],
    ["unknown", "Review SEO before publishing"],
  ] as const)(
    "shows the server's %s status without claiming verification",
    (status, label) => {
      const metadata = seoSchema.parse({ ...seo, review_status: status });
      render(<SeoPanel seo={metadata} saving={false} onSave={vi.fn()} />);
      const notice = screen.getByRole("region", { name: "SEO review status" });
      expect(within(notice).getByText(label)).toBeVisible();
      expect(notice).toHaveTextContent(/check/i);
      expect(notice).not.toHaveTextContent(/verified|perfect|fact.?checked/i);
    },
  );

  it("keeps fallback metadata marked for review until the server returns an edited snapshot", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);
    const fallback: Seo = { ...seo, review_status: "needs_review" };
    const view = render(<SeoPanel seo={fallback} saving={false} onSave={onSave} />);
    expect(screen.getByText("Needs review")).toBeVisible();
    expect(
      screen.getByText(/article may have changed, or SEO generation/i),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Edit SEO" }));
    await user.clear(screen.getByLabelText(/seo title/i));
    await user.paste("An edited Kerala guide");
    expect(screen.getByText("Needs review")).toBeVisible();
    expect(screen.getByText(/status applies to the saved version/i)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Save version" }));
    await screen.findByRole("button", { name: "Edit SEO" });
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ review_status: "needs_review" }),
    );
    expect(screen.getByText("Needs review")).toBeVisible();

    view.rerender(
      <SeoPanel
        seo={{ ...fallback, title: "An edited Kerala guide", review_status: "edited" }}
        saving={false}
        onSave={onSave}
      />,
    );
    expect(screen.getByText("Edited by you")).toBeVisible();
    expect(screen.queryByText("Needs review")).not.toBeInTheDocument();
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

  it("lets keywords be typed key by key without piling up spaces", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    render(<SeoPanel seo={seo} saving={false} onSave={onSave} />);
    await user.click(screen.getByRole("button", { name: /edit seo/i }));

    const keywords = screen.getByLabelText(/keywords/i);
    await user.type(keywords, ", houseboats, alleppey");
    expect(keywords).toHaveValue("kerala, travel, houseboats, alleppey");

    await user.click(screen.getByRole("button", { name: /save version/i }));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        keywords: ["kerala", "travel", "houseboats", "alleppey"],
      }),
    );
  });

  it("says when there are more than 15 keywords instead of dropping them", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    render(<SeoPanel seo={seo} saving={false} onSave={onSave} />);
    await user.click(screen.getByRole("button", { name: /edit seo/i }));

    const keywords = screen.getByLabelText(/keywords/i);
    const sixteen = Array.from({ length: 16 }, (_, i) => `word${i + 1}`).join(", ");
    await user.clear(keywords);
    await user.type(keywords, sixteen);

    expect(keywords).toHaveValue(sixteen);
    expect(keywords).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText(/remove 1 keyword/i)).toBeVisible();
    expect(screen.getByRole("button", { name: /save version/i })).toBeDisabled();
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
