"use client";

import { SEO_LIMITS, type Seo } from "@/lib/api/schemas";

function LengthMeter({ value, limit }: { value: number; limit: number }) {
  const over = value > limit;
  const near = value > limit * 0.9;
  return (
    <span
      className={`text-xs ${over ? "text-rose-400" : near ? "text-amber-400" : "text-emerald-400"}`}
    >
      {value}/{limit} {over ? "— too long for SERP display" : ""}
    </span>
  );
}

export default function SeoPanel({ seo }: { seo: Seo | null }) {
  if (!seo) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-400">
        SEO metadata will appear here after generation.
      </div>
    );
  }

  return (
    <div className="space-y-5 text-sm">
      <div>
        <div className="mb-1 flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-300">
            SEO Title
          </h3>
          <LengthMeter value={seo.title.length} limit={SEO_LIMITS.title} />
        </div>
        <p className="rounded-lg border border-slate-700 bg-slate-800 p-3 text-slate-100">
          {seo.title}
        </p>
      </div>

      <div>
        <div className="mb-1 flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-300">
            Meta Description
          </h3>
          <LengthMeter value={seo.description.length} limit={SEO_LIMITS.description} />
        </div>
        <p className="rounded-lg border border-slate-700 bg-slate-800 p-3 text-slate-100">
          {seo.description}
        </p>
      </div>

      <div>
        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-300">
          Keywords
        </h3>
        <ul className="flex flex-wrap gap-2">
          {seo.keywords.map((keyword) => (
            <li
              key={keyword}
              className="rounded-full border border-slate-600 bg-slate-900/70 px-2.5 py-1 text-xs text-slate-200"
            >
              {keyword}
            </li>
          ))}
        </ul>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-300">
            Open Graph Title
          </h3>
          <p className="rounded-lg border border-slate-700 bg-slate-800 p-3 text-slate-100">
            {seo.og_title ?? seo.title}
          </p>
        </div>
        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-300">
            Open Graph Description
          </h3>
          <p className="rounded-lg border border-slate-700 bg-slate-800 p-3 text-slate-100">
            {seo.og_description ?? seo.description}
          </p>
        </div>
      </div>
    </div>
  );
}
