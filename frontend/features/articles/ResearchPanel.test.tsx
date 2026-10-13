import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { articleContentSchema, type ArticleContent } from "@/lib/api/schemas";
import ResearchPanel from "./ResearchPanel";

const sourced: NonNullable<ArticleContent["research"]> = {
  status: "sources_retrieved",
  retrieved_at: "2026-10-13T09:00:00Z",
  sources: [
    {
      id: "source-1",
      title: "Growing herbs",
      url: "https://www.rhs.org.uk/herbs/growing",
      published_at: "2026-10-12",
    },
  ],
};

describe("ResearchPanel", () => {
  it("shows sources and separates retrieval from estimated publication without claiming verification", () => {
    render(<ResearchPanel research={sourced} />);
    const panel = screen.getByRole("region", { name: "Article sources" });
    expect(within(panel).getByRole("status")).toHaveTextContent("Sources retrieved.");
    expect(within(panel).getByRole("status")).toHaveTextContent(
      "does not guarantee complete coverage or confirm the latest social post",
    );
    const link = within(panel).getByRole("link", { name: "Growing herbs" });
    expect(within(panel).getByText("[source-1]", { exact: true })).toBeVisible();
    expect(link).toHaveAttribute("href", sourced.sources[0].url);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    const times = panel.querySelectorAll("time");
    expect(times[0]).toHaveAttribute("dateTime", sourced.retrieved_at);
    expect(times[0]).toHaveTextContent("13 Oct 2026, 09:00 UTC");
    expect(times[1]).toHaveAttribute("dateTime", "2026-10-12");
    expect(times[1]).toHaveTextContent("12 Oct 2026");
    expect(times[1]).not.toHaveTextContent("00:00");
    expect(panel).toHaveTextContent("Reported publication/update (estimated)");
  });

  it.each([
    undefined,
    { status: "unresearched", retrieved_at: null, sources: [] },
    { ...sourced, sources: [] },
  ])("keeps legacy, unresearched, and empty records honest", (research) => {
    render(<ResearchPanel research={research as ArticleContent["research"]} />);
    expect(screen.getByRole("status")).toHaveTextContent("Unresearched draft.");
    expect(screen.getByRole("status")).toHaveTextContent(
      "No live sources are recorded for this version",
    );
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(document.querySelector("time")).toBeNull();
  });

  it("does not turn unsafe, insecure, or credential-bearing source URLs into links", () => {
    const urls = [
      "javascript:alert(1)",
      "http://example.com",
      "https://user:secret@example.com",
      "not-a-url",
    ];
    render(
      <ResearchPanel
        research={{
          ...sourced,
          sources: urls.map((url, index) => ({
            id: String(index),
            title: `Source ${index}`,
            url,
          })),
        }}
      />,
    );
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getAllByText(/link unavailable/)).toHaveLength(urls.length);
    expect(document.body.innerHTML).not.toContain("user:secret");
  });

  it("omits missing or invalid dates without inventing publication information", () => {
    render(
      <ResearchPanel
        research={{
          ...sourced,
          retrieved_at: "invalid",
          sources: [{ ...sourced.sources[0], published_at: null }],
        }}
      />,
    );
    expect(document.querySelector("time")).toBeNull();
    expect(screen.queryByText(/Reported publication/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Retrieved:/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Growing herbs" })).toBeInTheDocument();
  });

  it("preserves optional publication metadata through API parsing while accepting older source records", () => {
    const content = {
      title: "Herbs",
      introduction: "Intro",
      sections: [],
      conclusion: "End",
      research: sourced,
    };
    const parsed = articleContentSchema.parse(content);
    expect(parsed.research?.sources[0].published_at).toBe("2026-10-12");
    const legacy = articleContentSchema.parse({
      ...content,
      research: {
        ...sourced,
        sources: [{ id: "legacy", title: "Source", url: "https://example.com" }],
      },
    });
    expect(legacy.research?.sources[0]).not.toHaveProperty("published_at");
  });
});
