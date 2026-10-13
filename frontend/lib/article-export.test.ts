import { afterEach, describe, expect, it, vi } from "vitest";
import { articleExportFilename, downloadArticleFile } from "./article-export";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("article downloads", () => {
  it("uses readable Unicode filenames and handles invalid or reserved names", () => {
    expect(articleExportFilename("मुंबई: a writer's guide?", "markdown")).toBe(
      "मुंबई a writer's guide.md",
    );
    expect(articleExportFilename(" CON.txt ", "html")).toBe("article-CON.txt.html");
    expect(articleExportFilename("///...", "markdown")).toBe("article.md");
    expect(articleExportFilename("😀".repeat(80), "markdown").replace(/\.md$/, "")).toBe(
      "😀".repeat(60),
    );
  });

  it("downloads the saved Markdown with provenance intact and removes its temporary anchor", async () => {
    vi.useFakeTimers();
    const source =
      "# Café\n\n[Primary source](https://example.com/source)\n\nUnresearched draft: verify claims.\n";
    let received: Blob | undefined;
    const revoke = vi.fn();
    vi.stubGlobal(
      "URL",
      Object.assign(class extends URL {}, {
        createObjectURL: vi.fn((blob: Blob) => {
          received = blob;
          return "blob:export-test";
        }),
        revokeObjectURL: revoke,
      }),
    );
    let filename = "";
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      expect(document.body.contains(this)).toBe(true);
      filename = this.download;
    });
    downloadArticleFile("Café", source, "markdown");
    expect(filename).toBe("Café.md");
    expect(received?.type).toBe("text/markdown;charset=utf-8");
    vi.useRealTimers();
    const reader = new FileReader();
    const content = new Promise((resolve) => {
      reader.onload = () => resolve(reader.result);
    });
    reader.readAsText(received!);
    vi.useRealTimers();
    expect(await content).toBe(source);
    expect(document.querySelector('a[download="Café.md"]')).toBeNull();
  });

  it("schedules URL cleanup even when the browser download fails", () => {
    vi.useFakeTimers();
    const revoke = vi.fn();
    vi.stubGlobal(
      "URL",
      Object.assign(class extends URL {}, {
        createObjectURL: vi.fn(() => "blob:failed"),
        revokeObjectURL: revoke,
      }),
    );
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(() => downloadArticleFile("Draft", "body", "html")).toThrow("blocked");
    expect(document.querySelector('a[download="Draft.html"]')).toBeNull();
    vi.runAllTimers();
    expect(revoke).toHaveBeenCalledWith("blob:failed");
  });
});
