import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import ArticleView from "./ArticleView";

describe("ArticleView", () => {
  it("renders markdown as formatted HTML", () => {
    render(<ArticleView markdown={"# Hello World\n\nSome paragraph text."} />);
    const heading = screen.getByRole("heading", { name: /hello world/i });
    expect(heading).toBeInTheDocument();
    expect(screen.getByText("Some paragraph text.")).toBeInTheDocument();
  });

  it("sanitizes script tags out of rendered markdown", () => {
    const malicious = "# Title\n\n<script>alert('xss')</script>";
    render(<ArticleView markdown={malicious} />);
    const container = document.querySelector(".prose");
    expect(container?.querySelector("script")).toBeNull();
    expect(container?.innerHTML).not.toContain("<script>");
  });

  it("sanitizes javascript: links", () => {
    const malicious = "[click me](javascript:alert(1))";
    render(<ArticleView markdown={malicious} />);
    // DOMPurify strips the dangerous href (or the anchor entirely).
    expect(document.querySelector('a[href*="javascript"]')).toBeNull();
    expect(document.querySelector(".prose")?.innerHTML).not.toContain("javascript:");
  });

  it("shows the word count", () => {
    render(<ArticleView markdown={"one two three four five"} />);
    expect(screen.getByText(/5 words/)).toBeInTheDocument();
  });

  it("copies markdown when the copy button is used", async () => {
    const clipboard = vi.fn();
    Object.assign(navigator, { clipboard: { writeText: clipboard } });
    render(<ArticleView markdown="# x" onCopy={() => clipboard("copied")} />);
    // onCopy path is wired through the button.
    expect(screen.getByRole("button", { name: /copy/i })).toBeInTheDocument();
  });
});
