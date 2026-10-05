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
      <div className="flex h-full items-center justify-center text-sm text-slate-500">
        The rendered HTML page will appear here after generation.
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="mb-3 flex items-center justify-between text-sm">
        <span className="font-medium text-slate-700">Live HTML preview</span>
        {onDownload ? (
          <button
            type="button"
            onClick={onDownload}
            className="flex items-center gap-1.5 rounded-lg border border-stone-300 px-3 py-1.5 text-slate-700 transition-colors hover:border-teal-600 hover:text-teal-800"
          >
            <Download aria-hidden className="h-4 w-4" /> Download HTML
          </button>
        ) : null}
      </div>
      <div className="min-h-0 flex-1 overflow-hidden rounded-lg border border-stone-200 bg-white">
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
