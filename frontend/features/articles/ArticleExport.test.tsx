import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import ArticleExport from "./ArticleExport";
import { downloadArticleFile } from "@/lib/article-export";

vi.mock("@/lib/article-export", () => ({ downloadArticleFile: vi.fn() }));
beforeEach(() => {
  vi.mocked(downloadArticleFile).mockReset();
});
const props = {
  title: "Saved title",
  html: "<h1>Saved</h1>",
  markdown: "# Saved\n\n[Source](https://example.com)",
};

describe("export controls", () => {
  it("offers both formats and exports the saved Markdown", () => {
    render(<ArticleExport {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Download Markdown" }));
    expect(downloadArticleFile).toHaveBeenCalledWith(
      props.title,
      props.markdown,
      "markdown",
    );
    fireEvent.click(screen.getByRole("button", { name: "Download HTML" }));
    expect(downloadArticleFile).toHaveBeenCalledWith(props.title, props.html, "html");
  });
  it("prevents stale exports while edits are unsaved", () => {
    render(<ArticleExport {...props} disabled />);
    expect(screen.getByRole("button", { name: "Download Markdown" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Download HTML" }));
    expect(downloadArticleFile).not.toHaveBeenCalled();
    expect(screen.getByRole("status")).toHaveTextContent("Save or discard");
  });
  it("shows a retryable error if a download cannot start", () => {
    vi.mocked(downloadArticleFile).mockImplementation(() => {
      throw new Error("blocked");
    });
    render(<ArticleExport {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Download Markdown" }));
    expect(screen.getByRole("alert")).toHaveTextContent("download could not start");
  });
});
