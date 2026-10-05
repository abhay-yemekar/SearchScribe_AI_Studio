"use client";

import { useState } from "react";
import { Save } from "lucide-react";

import { Spinner } from "@/components/shared/States";
import { SEO_LIMITS, type Seo } from "@/lib/api/schemas";

const field =
  "mt-1 w-full rounded-lg border border-slate-600 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500";

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

export default function SeoPanel({
  seo,
  saving,
  onSave,
}: {
  seo: Seo | null;
  saving: boolean;
  onSave: (seo: Seo) => void;
}) {
  const [draft, setDraft] = useState<Seo | null>(seo ? structuredClone(seo) : null);
  const [editing, setEditing] = useState(false);

  if (!seo || !draft) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-400">
        SEO metadata will appear here after generation.
      </div>
    );
  }

  if (editing) {
    return (
      <form
        className="space-y-5 text-sm"
        onSubmit={(event) => {
          event.preventDefault();
          onSave({
            ...draft,
            keywords: draft.keywords.map((keyword) => keyword.trim()).filter(Boolean),
            canonical_url: draft.canonical_url?.trim() || null,
          });
        }}
      >
        <label className="block text-xs font-semibold uppercase tracking-wide text-slate-300">
          <span className="flex items-center justify-between">
            SEO Title
            <LengthMeter value={draft.title.length} limit={SEO_LIMITS.title} />
          </span>
          <input
            className={field}
            value={draft.title}
            maxLength={200}
            required
            onChange={(event) => setDraft({ ...draft, title: event.target.value })}
          />
        </label>

        <label className="block text-xs font-semibold uppercase tracking-wide text-slate-300">
          <span className="flex items-center justify-between">
            Meta Description
            <LengthMeter
              value={draft.description.length}
              limit={SEO_LIMITS.description}
            />
          </span>
          <textarea
            className={`${field} min-h-24`}
            value={draft.description}
            maxLength={400}
            required
            onChange={(event) => setDraft({ ...draft, description: event.target.value })}
          />
        </label>

        <label className="block text-xs font-semibold uppercase tracking-wide text-slate-300">
          Keywords
          <input
            className={field}
            value={draft.keywords.join(", ")}
            required
            placeholder="travel, kerala, backwaters"
            onChange={(event) =>
              setDraft({ ...draft, keywords: event.target.value.split(",").slice(0, 15) })
            }
          />
          <span className="mt-1 block font-normal normal-case text-slate-500">
            Separate up to 15 keywords with commas.
          </span>
        </label>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-300">
            Open Graph Title
            <input
              className={field}
              value={draft.og_title ?? ""}
              maxLength={200}
              onChange={(event) =>
                setDraft({ ...draft, og_title: event.target.value || null })
              }
            />
          </label>
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-300">
            Robots
            <select
              className={field}
              value={draft.robots}
              onChange={(event) =>
                setDraft({ ...draft, robots: event.target.value as Seo["robots"] })
              }
            >
              <option value="index, follow">Index and follow</option>
              <option value="noindex, follow">Do not index</option>
            </select>
          </label>
        </div>

        <label className="block text-xs font-semibold uppercase tracking-wide text-slate-300">
          Open Graph Description
          <textarea
            className={`${field} min-h-20`}
            value={draft.og_description ?? ""}
            maxLength={400}
            onChange={(event) =>
              setDraft({ ...draft, og_description: event.target.value || null })
            }
          />
        </label>

        <label className="block text-xs font-semibold uppercase tracking-wide text-slate-300">
          Canonical URL
          <input
            className={field}
            value={draft.canonical_url ?? ""}
            type="url"
            maxLength={500}
            placeholder="https://example.com/article"
            onChange={(event) =>
              setDraft({ ...draft, canonical_url: event.target.value || null })
            }
          />
        </label>

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={() => {
              setDraft(structuredClone(seo));
              setEditing(false);
            }}
            className="rounded-lg border border-slate-600 px-4 py-2 hover:bg-slate-800"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving || draft.keywords.every((keyword) => !keyword.trim())}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 font-medium hover:bg-blue-700 disabled:opacity-60"
          >
            {saving ? <Spinner /> : <Save className="h-4 w-4" />}
            {saving ? "Saving…" : "Save version"}
          </button>
        </div>
      </form>
    );
  }

  return (
    <div className="space-y-5 text-sm">
      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="rounded-lg bg-blue-600 px-3 py-1.5 font-medium hover:bg-blue-700"
        >
          Edit SEO
        </button>
      </div>
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
            Robots
          </h3>
          <p className="rounded-lg border border-slate-700 bg-slate-800 p-3 text-slate-100">
            {seo.robots}
          </p>
        </div>
      </div>

      <div>
        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-300">
          Open Graph Description
        </h3>
        <p className="rounded-lg border border-slate-700 bg-slate-800 p-3 text-slate-100">
          {seo.og_description ?? seo.description}
        </p>
      </div>

      {seo.canonical_url ? (
        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-300">
            Canonical URL
          </h3>
          <a
            href={seo.canonical_url}
            target="_blank"
            rel="noreferrer"
            className="block break-all rounded-lg border border-slate-700 bg-slate-800 p-3 text-blue-300 hover:text-blue-200"
          >
            {seo.canonical_url}
          </a>
        </div>
      ) : null}
    </div>
  );
}
