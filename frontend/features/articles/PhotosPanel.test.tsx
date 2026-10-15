import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ArticleDetail } from "@/lib/api/schemas";
import { searchArticlePhotos } from "@/lib/api/articles";
import PhotosPanel from "./PhotosPanel";

vi.mock("@/lib/api/articles", () => ({ searchArticlePhotos: vi.fn() }));
const photo = {
  provider: "commons" as const,
  source_id: 123,
  title: "Canal.jpg",
  creator: "Photo Author",
  source_url: "https://commons.wikimedia.org/wiki/File:Canal.jpg",
  preview_url: "https://upload.wikimedia.org/wikipedia/commons/a/ab/Canal.jpg",
  original_url: "https://upload.wikimedia.org/wikipedia/commons/a/ab/Canal.jpg",
  license_name: "CC BY 4.0",
  license_url: "https://creativecommons.org/licenses/by/4.0/",
  width: 4032,
  height: 2688,
  selection_token: "test-selection",
};
const article: ArticleDetail = {
  id: 7,
  title: "A canal story",
  query: "Kerala canals",
  status: "ready",
  current_version: 1,
  content: {
    title: "A canal story",
    introduction: "Intro",
    sections: [
      { id: "section01", heading: "Travel slowly", paragraphs: ["Text"], bullets: [] },
    ],
    conclusion: "End",
  },
  markdown: "# Story",
  html: "<p>Story</p>",
  seo: null,
  created_at: "2026-10-15",
  updated_at: "2026-10-15",
};

describe("PhotosPanel", () => {
  beforeEach(() => vi.clearAllMocks());
  it("searches only on explicit submission and retains credits and edited alt text", async () => {
    vi.mocked(searchArticlePhotos).mockResolvedValue({
      query: "Kerala canals",
      photos: [photo],
    });
    const onSave = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(
      <PhotosPanel
        article={article}
        saving={false}
        onSave={onSave}
        onDraftChange={vi.fn()}
        requestDiscard={vi.fn()}
      />,
    );
    expect(searchArticlePhotos).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Choose photos" }));
    await user.click(screen.getByRole("button", { name: "Search photos" }));
    expect(await screen.findByText("4032 × 2688 · 4K original")).toBeVisible();
    expect(searchArticlePhotos).toHaveBeenCalledWith(7, "Kerala canals");
    await user.click(screen.getByRole("button", { name: "Select" }));
    const alt = screen.getByLabelText(/Alt text/);
    await user.clear(alt);
    await user.type(alt, "Palm trees above the canal");
    await user.selectOptions(screen.getByLabelText("Position"), "section01");
    await user.click(screen.getByRole("button", { name: "Save photos" }));
    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith([
        expect.objectContaining({
          alt: "Palm trees above the canal",
          section_id: "section01",
          selection_token: "test-selection",
          asset: expect.objectContaining({
            creator: "Photo Author",
            license_name: "CC BY 4.0",
          }),
        }),
      ]),
    );
  });
  it("shows an honest empty result and never substitutes unrelated stock images", async () => {
    vi.mocked(searchArticlePhotos).mockResolvedValue({
      query: "Kerala canals",
      photos: [],
    });
    const user = userEvent.setup();
    render(
      <PhotosPanel
        article={article}
        saving={false}
        onSave={vi.fn()}
        onDraftChange={vi.fn()}
        requestDiscard={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Choose photos" }));
    await user.click(screen.getByRole("button", { name: "Search photos" }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "No suitable licensed photos found",
    );
    expect(screen.queryByRole("button", { name: "Select" })).not.toBeInTheDocument();
  });
  it("retains pending edits on a failed save and uses the workspace discard guard", async () => {
    const user = userEvent.setup();
    const discard = vi.fn();
    const withPhoto = {
      ...article,
      content: {
        ...article.content,
        photos: [{ ...photo, id: "a".repeat(32), section_id: null, alt: "Canal" }],
      },
    };
    const onSave = vi.fn().mockRejectedValue(new Error("Conflict"));
    render(
      <PhotosPanel
        article={withPhoto}
        saving={false}
        onSave={onSave}
        onDraftChange={vi.fn()}
        requestDiscard={discard}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Edit photos" }));
    await user.type(screen.getByLabelText(/Alt text/), " in Kerala");
    await user.click(screen.getByRole("button", { name: "Save photos" }));
    await waitFor(() => expect(onSave).toHaveBeenCalledOnce());
    expect(screen.getByLabelText(/Alt text/)).toHaveValue("Canal in Kerala");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(discard).toHaveBeenCalledWith(expect.any(Function));
  });
});
