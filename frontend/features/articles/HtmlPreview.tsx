"use client";

import { Download } from "lucide-react";

export default function HtmlPreview({
  html,
  title,
  onDownload,
}: {
  html: string;
  title: string;
  onDownload?: () => void;
}) {
  if (!html) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-400">
        The rendered HTML page will appear here after generation.
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="mb-2 flex items-center justify-between text-sm">
        <span className="text-slate-300">Live HTML preview</span>
        {onDownload ? (
          <button
            type="button"
            onClick={onDownload}
            className="flex items-center gap-1.5 rounded border border-slate-600 px-3 py-1 transition-colors hover:bg-slate-800"
          >
            <Download aria-hidden className="h-4 w-4" /> Download HTML
          </button>
        ) : null}
      </div>
      <div className="min-h-0 flex-1 overflow-hidden rounded-lg border border-slate-700 bg-white">
        {/* Sandbox: no scripts, no same-origin access — preview only. */}
        <iframe
          title={`HTML preview of ${title}`}
          srcDoc={html}
          className="h-full w-full bg-white"
          sandbox=""
        />
      </div>
    </div>
  );
}
