"use client";

import { useMemo } from "react";
import { marked } from "marked";
import DOMPurify from "dompurify";
import { Copy } from "lucide-react";

/** Renders article markdown as sanitized HTML (DOMPurify strips any XSS). */
export default function ArticleView({
  markdown,
  onCopy,
}: {
  markdown: string;
  onCopy?: () => void;
}) {
  const html = useMemo(() => {
    const raw = marked.parse(markdown, { async: false }) as string;
    return DOMPurify.sanitize(raw, { USE_PROFILES: { html: true } });
  }, [markdown]);

  const words = markdown.trim() ? markdown.trim().split(/\s+/).length : 0;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="mb-2 flex items-center justify-between text-xs text-slate-400">
        <span aria-live="polite">{words.toLocaleString()} words</span>
        {onCopy ? (
          <button
            type="button"
            onClick={onCopy}
            className="flex items-center gap-1 rounded border border-slate-600 px-2 py-1 transition-colors hover:bg-slate-800"
          >
            <Copy aria-hidden className="h-3.5 w-3.5" /> Copy
          </button>
        ) : null}
      </div>
      <div
        className="prose prose-invert min-h-0 max-w-none flex-1 overflow-y-auto rounded-lg border border-slate-700 bg-slate-800/60 p-6 text-sm leading-relaxed"
        // Safe: DOMPurify sanitized above.
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}
