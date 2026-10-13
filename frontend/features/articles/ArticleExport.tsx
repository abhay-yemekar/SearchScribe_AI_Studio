"use client";

import { useState } from "react";
import { Download, FileText } from "lucide-react";
import { downloadArticleFile, type ArticleExportFormat } from "@/lib/article-export";

export default function ArticleExport({
  title,
  html,
  markdown,
  disabled = false,
}: {
  title: string;
  html: string;
  markdown: string;
  disabled?: boolean;
}) {
  const [error, setError] = useState<string | null>(null);
  function download(format: ArticleExportFormat) {
    if (disabled) return;
    setError(null);
    try {
      downloadArticleFile(title, format === "markdown" ? markdown : html, format);
    } catch {
      setError("The download could not start. Please try again.");
    }
  }
  const buttonClass =
    "inline-flex items-center gap-1.5 rounded-lg border border-stone-300 bg-white px-3 py-2 text-xs font-medium text-slate-700 transition-colors hover:border-teal-700 hover:text-teal-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700 disabled:cursor-not-allowed disabled:opacity-50";
  return (
    <div
      role="group"
      aria-label="Export article"
      className="flex flex-wrap items-center gap-2"
    >
      <button
        type="button"
        aria-label="Download HTML"
        disabled={disabled}
        onClick={() => download("html")}
        className={buttonClass}
      >
        <Download aria-hidden className="h-4 w-4" /> HTML
      </button>
      <button
        type="button"
        aria-label="Download Markdown"
        disabled={disabled}
        onClick={() => download("markdown")}
        className={buttonClass}
      >
        <FileText aria-hidden className="h-4 w-4" /> Markdown
      </button>
      {disabled && (
        <p role="status" className="w-full text-xs text-slate-600">
          Save or discard your changes before exporting.
        </p>
      )}
      {error && (
        <p role="alert" className="w-full text-xs text-rose-700">
          {error}
        </p>
      )}
    </div>
  );
}
