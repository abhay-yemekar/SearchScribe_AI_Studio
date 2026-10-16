import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

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

  it("does not discard dirty edits until confirmed and keeps focus on the safe choice", async () => {
    const user = userEvent.setup();
    render(<ArticleEditor content={content} saving={false} onSave={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /edit article/i }));
    await user.type(screen.getByLabelText("Title"), " changed");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(
      screen.getByRole("dialog", { name: "Discard unsaved changes?" }),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Keep editing" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Keep editing" }));
    expect(screen.getByLabelText("Title")).toHaveValue("Original title changed");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await user.click(screen.getByRole("button", { name: "Discard changes" }));
    expect(screen.getByRole("button", { name: /edit article/i })).toBeVisible();
    await user.click(screen.getByRole("button", { name: /edit article/i }));
    expect(screen.getByLabelText("Title")).toHaveValue("Original title");
  });

  it("allows unchanged cancellation without a warning, including reverted edits", async () => {
    const user = userEvent.setup();
    render(<ArticleEditor content={content} saving={false} onSave={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /edit article/i }));
    expect(screen.getByRole("button", { name: /save version/i })).toBeDisabled();
    await user.type(screen.getByLabelText("Title"), "x");
    await user.keyboard("{Backspace}");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /edit article/i })).toBeVisible();
  });

  it("retains an edited draft on external refresh and failed save", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockRejectedValue(new Error("Newer version exists"));
    const view = render(
      <ArticleEditor content={content} saving={false} onSave={onSave} />,
    );
    await user.click(screen.getByRole("button", { name: /edit article/i }));
    await user.type(screen.getByLabelText("Title"), " changed");
    view.rerender(
      <ArticleEditor
        content={{ ...content, introduction: "New server introduction" }}
        saving={false}
        onSave={onSave}
      />,
    );
    expect(screen.getByLabelText("Introduction")).toHaveValue(content.introduction);
    await user.click(screen.getByRole("button", { name: /save version/i }));
    expect(screen.getByLabelText("Title")).toHaveValue("Original title changed");
    expect(screen.getByLabelText("Introduction")).toHaveValue(content.introduction);
  });

  it("lets paragraphs and bullets be typed key by key, including new lines", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    render(<ArticleEditor content={content} saving={false} onSave={onSave} />);
    await user.click(screen.getByRole("button", { name: /edit article/i }));

    const paragraphs = screen.getByLabelText("Section 1 paragraphs");
    await user.type(paragraphs, "{Enter}{Enter}Second paragraph");
    expect(paragraphs).toHaveValue("Text\n\nSecond paragraph");

    const bullets = screen.getByLabelText("Section 1 bullets");
    await user.type(bullets, "First point {Enter}Second point");
    expect(bullets).toHaveValue("First point \nSecond point");

    await user.click(screen.getByRole("button", { name: /save version/i }));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        sections: [
          expect.objectContaining({
            paragraphs: ["Text", "Second paragraph"],
            bullets: ["First point", "Second point"],
          }),
        ],
      }),
    );
  });

  it("tidies list text on blur and restores it when edits are discarded", async () => {
    const user = userEvent.setup();
    render(<ArticleEditor content={content} saving={false} onSave={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /edit article/i }));

    const bullets = screen.getByLabelText("Section 1 bullets");
    await user.type(bullets, "  One {Enter}{Enter}Two  ");
    await user.tab();
    expect(bullets).toHaveValue("One\nTwo");

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await user.click(screen.getByRole("button", { name: "Discard changes" }));
    await user.click(screen.getByRole("button", { name: /edit article/i }));
    expect(screen.getByLabelText("Section 1 bullets")).toHaveValue("");
  });

  it("disables all editing controls while saving", async () => {
    const user = userEvent.setup();
    const view = render(
      <ArticleEditor content={content} saving={false} onSave={vi.fn()} />,
    );
    await user.click(screen.getByRole("button", { name: /edit article/i }));
    view.rerender(<ArticleEditor content={content} saving onSave={vi.fn()} />);
    expect(screen.getByLabelText("Title")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /add section/i })).toBeDisabled();
  });
});
