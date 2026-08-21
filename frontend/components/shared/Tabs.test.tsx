import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import Tabs from "./Tabs";

const tabs = [
  { key: "article", label: "Article", content: <p>article panel</p> },
  { key: "seo", label: "SEO Metadata", content: <p>seo panel</p> },
];

function renderTabs(active = "article", onChange = () => {}) {
  return render(<Tabs tabs={tabs} active={active} onChange={onChange} />);
}

describe("Tabs", () => {
  it("renders a tablist with accessible tabs", () => {
    renderTabs();
    expect(screen.getByRole("tablist")).toBeInTheDocument();
    expect(screen.getByRole("tab", { selected: true, name: /article/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { selected: false, name: /seo/i })).toBeInTheDocument();
  });

  it("shows the active panel content", () => {
    renderTabs();
    expect(screen.getByRole("tabpanel")).toHaveTextContent("article panel");
  });

  it("calls onChange when a tab is clicked", () => {
    const onChange = vi.fn();
    renderTabs("article", onChange);
    fireEvent.click(screen.getByRole("tab", { name: /seo/i }));
    expect(onChange).toHaveBeenCalledWith("seo");
  });

  it("switches tabs with arrow keys", () => {
    const onChange = vi.fn();
    renderTabs("article", onChange);
    fireEvent.keyDown(screen.getByRole("tablist"), { key: "ArrowRight" });
    expect(onChange).toHaveBeenCalledWith("seo");
  });
});
