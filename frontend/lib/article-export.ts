"use client";

export type ArticleExportFormat = "html" | "markdown";

export function articleExportFilename(
  title: string,
  format: ArticleExportFormat,
): string {
  let name = Array.from(title.normalize("NFKC"))
    .filter((character) => {
      const code = character.codePointAt(0)!;
      return code > 31 && code !== 127 && !'<>:"/\\|?*'.includes(character);
    })
    .join("")
    .trim();
  name =
    Array.from(name)
      .slice(0, 60)
      .join("")
      .replace(/[. ]+$/, "") || "article";
  if (/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(name))
    name = `article-${name}`;
  return `${name}.${format === "markdown" ? "md" : "html"}`;
}

/** Download the server's saved snapshot, including its source attribution. */
export function downloadArticleFile(
  title: string,
  content: string,
  format: ArticleExportFormat,
): void {
  const type =
    format === "markdown" ? "text/markdown;charset=utf-8" : "text/html;charset=utf-8";
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = articleExportFilename(title, format);
  anchor.rel = "noopener";
  try {
    document.body.appendChild(anchor);
    anchor.click();
  } finally {
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
