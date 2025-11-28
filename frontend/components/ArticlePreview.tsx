// article preview placeholder
"use client";

import { useMemo } from "react";
import { marked } from "marked";

type ArticlePreviewProps = {
  /** Raw article text coming from backend (Markdown-style) */
  content: string;
};

export default function ArticlePreview({ content }: ArticlePreviewProps) {
  // Convert markdown → HTML only when content changes
  const html = useMemo(
    () => (content ? (marked.parse(content) as string) : ""),
    [content]
  );

  // If there is no content yet, show a soft placeholder
  if (!content.trim()) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-slate-800 border border-slate-700 rounded text-slate-400 text-sm">
        AI-generated article will appear here…
      </div>
    );
  }

  return (
    <div className="w-full h-full bg-slate-800 border border-slate-700 rounded p-6 overflow-y-auto text-sm leading-relaxed space-y-3">
      <div
        className="prose prose-invert max-w-none space-y-3"
        // We already control the source (LLM text), so this is acceptable here
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}
