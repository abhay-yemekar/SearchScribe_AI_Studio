"use client";

import { Save } from "lucide-react";

import { Spinner } from "@/components/shared/States";
import { SEO_LIMITS, type Seo } from "@/lib/api/schemas";
import DiscardChangesDialog from "./DiscardChangesDialog";
import { commaListCodec, RawInput } from "./RawTextField";
import { useEditorDraft, type EditorDraft } from "./useEditorDraft";

const MAX_KEYWORDS = 15;

const field =
  "mt-1 w-full rounded-lg border border-stone-300 bg-stone-50 px-3 py-2 text-sm text-slate-900 outline-hidden focus:border-teal-600 focus:ring-2 focus:ring-teal-100";

function LengthMeter({ value, limit }: { value: number; limit: number }) {
  const over = value > limit;
  const near = value > limit * 0.9;
  return (
    <span
      className={`text-xs ${over ? "text-rose-700" : near ? "text-amber-700" : "text-teal-700"}`}
    >
      {value}/{limit} {over ? "— too long for SERP display" : ""}
    </span>
  );
}

function SeoReviewStatus({ seo, editing = false }: { seo: Seo; editing?: boolean }) {
  const status = seo.review_status ?? "unknown";
  const messages = {
    generated: {
      title: "AI draft — review before publishing",
      description:
        "Check the title, description, and keywords against the article before publishing.",
    },
    needs_review: {
      title: "Needs review",
      description:
        "These details need another review: the article may have changed, or SEO generation could not complete. Edit the title, description, and keywords before publishing.",
    },
    edited: {
      title: "Edited by you",
      description:
        "Your edits are saved. Check accuracy and search display before publishing.",
    },
    unknown: {
      title: "Review SEO before publishing",
      description:
        "The source of this metadata is not recorded. Check the title, description, and keywords before publishing.",
    },
  };
  const message = messages[status];

  return (
    <section
      aria-label="SEO review status"
      className="rounded-lg border border-stone-200 bg-stone-50 px-4 py-3 text-slate-800"
    >
      <h3 className="font-semibold text-slate-900">{message.title}</h3>
      <p className="mt-1 text-sm leading-relaxed">{message.description}</p>
      {editing ? (
        <p className="mt-2 text-xs text-slate-600">
          This status applies to the saved version. Your changes have not been saved.
        </p>
      ) : null}
    </section>
  );
}

export default function SeoPanel({
  seo,
  saving,
  onSave,
  initialDraft,
  onDraftChange,
  requestDiscard,
}: {
  seo: Seo | null;
  saving: boolean;
  onSave: (seo: Seo) => void | Promise<void>;
  initialDraft?: EditorDraft<Seo | null>;
  onDraftChange?: (draft: EditorDraft<Seo | null>) => void;
  requestDiscard?: (action: () => void) => void;
}) {
  const {
    draft,
    editing,
    dirty,
    change: setDraft,
    start,
    cancel,
    submit,
    confirmCancel,
    keep,
    discard,
  } = useEditorDraft<Seo | null>({
    source: seo,
    saving,
    initialDraft,
    onDraftChange,
    requestDiscard,
    onSave: (value) => (value ? onSave(value) : undefined),
  });

  if (!seo || !draft) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-500">
        SEO metadata will appear here after generation.
      </div>
    );
  }

  if (editing) {
    const extraKeywords = draft.keywords.length - MAX_KEYWORDS;
    return (
      <form
        className="mx-auto max-w-3xl space-y-5 text-sm"
        onSubmit={(event) => {
          event.preventDefault();
          void submit({
            ...draft,
            keywords: draft.keywords.map((keyword) => keyword.trim()).filter(Boolean),
            canonical_url: draft.canonical_url?.trim() || null,
          });
        }}
      >
        <SeoReviewStatus seo={seo} editing />
        <fieldset disabled={saving} className="space-y-5">
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
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

          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
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
              onChange={(event) =>
                setDraft({ ...draft, description: event.target.value })
              }
            />
          </label>

          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
            Keywords
            <RawInput
              className={field}
              value={draft.keywords}
              codec={commaListCodec}
              required
              placeholder="travel, kerala, backwaters"
              aria-invalid={extraKeywords > 0}
              aria-describedby="seo-keywords-help"
              onValueChange={(keywords) => setDraft({ ...draft, keywords })}
            />
            <span
              id="seo-keywords-help"
              className={`mt-1 block font-normal normal-case ${
                extraKeywords > 0 ? "text-rose-700" : "text-slate-500"
              }`}
            >
              {extraKeywords > 0
                ? `Remove ${extraKeywords} keyword${extraKeywords === 1 ? "" : "s"}: up to ${MAX_KEYWORDS} are allowed.`
                : `Separate up to ${MAX_KEYWORDS} keywords with commas.`}
            </span>
          </label>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
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
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
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

          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
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

          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
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
              onClick={cancel}
              className="rounded-lg border border-stone-300 px-4 py-2 text-slate-700 hover:bg-stone-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={
                saving ||
                !dirty ||
                draft.keywords.every((keyword) => !keyword.trim()) ||
                extraKeywords > 0
              }
              className="flex items-center gap-2 rounded-lg bg-teal-700 px-4 py-2 font-medium text-white hover:bg-teal-800 disabled:opacity-60"
            >
              {saving ? <Spinner /> : <Save className="h-4 w-4" />}
              {saving ? "Saving…" : "Save version"}
            </button>
          </div>
        </fieldset>
        {confirmCancel ? (
          <DiscardChangesDialog onKeep={keep} onDiscard={discard} />
        ) : null}
      </form>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5 text-sm">
      <SeoReviewStatus seo={seo} />
      <div className="flex justify-end">
        <button
          type="button"
          onClick={start}
          disabled={saving}
          className="rounded-lg bg-teal-700 px-3 py-1.5 font-medium text-white hover:bg-teal-800"
        >
          Edit SEO
        </button>
      </div>
      <div>
        <div className="mb-1 flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-600">
            SEO Title
          </h3>
          <LengthMeter value={seo.title.length} limit={SEO_LIMITS.title} />
        </div>
        <p className="rounded-lg border border-stone-200 bg-stone-50 p-3 text-slate-800">
          {seo.title}
        </p>
      </div>

      <div>
        <div className="mb-1 flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-600">
            Meta Description
          </h3>
          <LengthMeter value={seo.description.length} limit={SEO_LIMITS.description} />
        </div>
        <p className="rounded-lg border border-stone-200 bg-stone-50 p-3 text-slate-800">
          {seo.description}
        </p>
      </div>

      <div>
        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-600">
          Keywords
        </h3>
        <ul className="flex flex-wrap gap-2">
          {seo.keywords.map((keyword) => (
            <li
              key={keyword}
              className="rounded-full border border-teal-200 bg-teal-50 px-2.5 py-1 text-xs text-teal-800"
            >
              {keyword}
            </li>
          ))}
        </ul>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-600">
            Open Graph Title
          </h3>
          <p className="rounded-lg border border-stone-200 bg-stone-50 p-3 text-slate-800">
            {seo.og_title ?? seo.title}
          </p>
        </div>
        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-600">
            Robots
          </h3>
          <p className="rounded-lg border border-stone-200 bg-stone-50 p-3 text-slate-800">
            {seo.robots}
          </p>
        </div>
      </div>

      <div>
        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-600">
          Open Graph Description
        </h3>
        <p className="rounded-lg border border-stone-200 bg-stone-50 p-3 text-slate-800">
          {seo.og_description ?? seo.description}
        </p>
      </div>

      {seo.canonical_url ? (
        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-600">
            Canonical URL
          </h3>
          <a
            href={seo.canonical_url}
            target="_blank"
            rel="noreferrer"
            className="block break-all rounded-lg border border-stone-200 bg-stone-50 p-3 text-teal-700 hover:text-teal-900"
          >
            {seo.canonical_url}
          </a>
        </div>
      ) : null}
    </div>
  );
}
