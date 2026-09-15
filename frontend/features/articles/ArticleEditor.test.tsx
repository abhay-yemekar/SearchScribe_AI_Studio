import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ArticleEditor from "./ArticleEditor";

const content = {
  title: "Original title",
  introduction: "Original introduction",
  sections: [
    { id: "section01", heading: "First section", paragraphs: ["Text"], bullets: [] },
  ],
  conclusion: "Original conclusion",
};

describe("ArticleEditor", () => {
  it("saves a structured edit without mutating the loaded version", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    render(<ArticleEditor content={content} saving={false} onSave={onSave} />);

    await user.click(screen.getByRole("button", { name: /edit article/i }));
    const title = screen.getByLabelText("Title");
    await user.clear(title);
    await user.type(title, "A better title");
    await user.click(screen.getByRole("button", { name: /save version/i }));

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ title: "A better title" }),
    );
    expect(content.title).toBe("Original title");
  });
});
