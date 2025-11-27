"use client";

interface HtmlPreviewProps {
  html: string;
  onDownload?: () => void;
}

export default function HtmlPreview({
  html,
  onDownload,
}: HtmlPreviewProps) {
  if (!html) {
    return (
      <div className="w-full h-full flex items-center justify-center text-slate-400 text-sm">
        HTML preview will appear here once content is generated.
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between mb-2 text-sm">
        <span className="text-slate-300">
          Live HTML Preview
        </span>
        <button
          onClick={onDownload}
          disabled={!onDownload}
          className="px-3 py-1 rounded border border-slate-600 hover:bg-slate-800 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          Download HTML
        </button>
      </div>

      {/* Iframe preview */}
      <div className="flex-1 border border-slate-700 rounded-lg overflow-hidden bg-slate-900">
        <iframe
          title="HTML Preview"
          srcDoc={html}
          className="w-full h-full bg-white"
          sandbox=""
        />
      </div>
    </div>
  );
}
