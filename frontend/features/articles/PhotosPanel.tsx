"use client";

import { useMemo, useState } from "react";
import Image from "next/image";
import { Camera, ExternalLink, Plus, Search, Trash2 } from "lucide-react";
import { ErrorBanner, Spinner } from "@/components/shared/States";
import { searchArticlePhotos } from "@/lib/api/articles";
import type {
  ArticleDetail,
  PhotoAsset,
  PhotoChoice,
  PhotoSuggestion,
} from "@/lib/api/schemas";
import { useEditorDraft, type EditorDraft } from "./useEditorDraft";
import PhotoFigure from "./PhotoFigure";
import DiscardChangesDialog from "./DiscardChangesDialog";

export type PhotoDraft = PhotoChoice & { asset: PhotoAsset };
const field =
  "mt-1 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-teal-700 focus:outline-none focus:ring-2 focus:ring-teal-100";

export default function PhotosPanel({
  article,
  saving,
  onSave,
  initialDraft,
  onDraftChange,
  requestDiscard,
}: {
  article: ArticleDetail;
  saving: boolean;
  onSave: (photos: PhotoDraft[]) => Promise<void>;
  initialDraft?: EditorDraft<PhotoDraft[]>;
  onDraftChange: (draft: EditorDraft<PhotoDraft[]>) => void;
  requestDiscard: (action: () => void) => void;
}) {
  const source = useMemo(
    () =>
      (article.content.photos ?? []).map((photo) => ({
        asset: photo,
        id: photo.id,
        alt: photo.alt,
        section_id: photo.section_id,
      })),
    [article.content.photos],
  );
  const editor = useEditorDraft<PhotoDraft[]>({
    source,
    saving,
    onSave,
    initialDraft,
    onDraftChange,
    requestDiscard,
  });
  const [query, setQuery] = useState(
    (article.seo?.keywords[0] || article.query).slice(0, 120),
  );
  const [results, setResults] = useState<PhotoSuggestion[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultQuery, setResultQuery] = useState("");
  const positions = [
    { id: null, label: "Cover · before the introduction" },
    ...article.content.sections.map((section) => ({
      id: section.id,
      label: section.heading,
    })),
  ];

  async function search(event: React.FormEvent) {
    event.preventDefault();
    if (searching || saving || query.trim().length < 3) return;
    setSearching(true);
    setSearched(false);
    setResults([]);
    setError(null);
    try {
      const response = await searchArticlePhotos(article.id, query.trim());
      setResults(response.photos);
      setResultQuery(response.query);
      setSearched(true);
    } catch (failure) {
      setError(
        failure instanceof Error ? failure.message : "Photo search failed. Try again.",
      );
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-stone-200 pb-5">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[.18em] text-teal-800">
            The visual edit
          </p>
          <h3 className="mt-2 text-2xl font-semibold tracking-tight text-[#17252b]">
            A photo that belongs in your story.
          </h3>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-slate-600">
            Choose a cover or section photo. Credits travel with every saved version and
            export.
          </p>
        </div>
        {!editor.editing && (
          <button
            type="button"
            onClick={editor.start}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-lg bg-[#17252b] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            <Camera className="h-4 w-4" aria-hidden />
            {source.length ? "Edit photos" : "Choose photos"}
          </button>
        )}
      </div>

      {!editor.editing ? (
        source.length ? (
          source.map((photo) => (
            <PhotoFigure key={photo.id} photo={photo.asset} alt={photo.alt} />
          ))
        ) : (
          <div className="rounded-xl border border-dashed border-stone-300 bg-stone-50 px-6 py-10 text-center text-sm text-slate-600">
            <Camera className="mx-auto mb-3 h-8 w-8 text-stone-400" aria-hidden />
            No photos yet. Keep it text-only, or choose a photo when it adds to the
            article.
          </div>
        )
      ) : (
        <>
          <form
            onSubmit={search}
            className="rounded-xl border border-stone-200 bg-stone-50 p-4"
          >
            <label
              htmlFor="photo-search"
              className="text-xs font-semibold uppercase tracking-wide text-slate-600"
            >
              Search Wikimedia Commons
            </label>
            <div className="mt-1 flex flex-wrap gap-2">
              <input
                id="photo-search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                maxLength={120}
                minLength={3}
                required
                className={`${field} mt-0 min-w-0 flex-1 basis-48`}
                placeholder="A place, subject, or visual idea"
              />
              <button
                type="submit"
                disabled={searching || saving || query.trim().length < 3}
                className="inline-flex items-center gap-2 rounded-lg bg-teal-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {searching ? <Spinner /> : <Search className="h-4 w-4" aria-hidden />}{" "}
                Search photos
              </button>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-slate-500">
              Only your search words are sent to Commons. Results are illustrative; check
              the file page for relevance, license and any additional restrictions.
            </p>
          </form>
          {error && <ErrorBanner message={error} />}
          {searched && (
            <p role="status" className="text-xs text-slate-500">
              {results.length
                ? `${results.length} results for “${resultQuery}”`
                : "No suitable licensed photos found. Try a broader subject or place."}
            </p>
          )}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {results.map((photo) => {
              const used = editor.draft.some(
                (item) => item.asset.source_id === photo.source_id,
              );
              const slot = positions.find(
                (position) =>
                  !editor.draft.some((item) => item.section_id === position.id),
              );
              return (
                <article
                  key={photo.source_id}
                  className="overflow-hidden rounded-xl border border-stone-200 bg-white"
                >
                  <Image
                    src={photo.preview_url}
                    alt={photo.title}
                    width={photo.width}
                    height={photo.height}
                    unoptimized
                    className="aspect-[4/3] w-full object-cover"
                    referrerPolicy="no-referrer"
                  />
                  <div className="space-y-2 p-3">
                    <p className="line-clamp-2 text-sm font-medium text-slate-800">
                      {photo.title}
                    </p>
                    <p className="text-[11px] text-slate-500">
                      {photo.width} × {photo.height}
                      {photo.width >= 3840 && photo.height >= 2160
                        ? " · 4K original"
                        : ""}
                    </p>
                    <p className="line-clamp-2 text-xs text-slate-600">
                      {photo.creator} · {photo.license_name}
                    </p>
                    <div className="flex items-center justify-between gap-2 pt-1">
                      <a
                        href={photo.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-teal-800 underline underline-offset-2"
                      >
                        File & license <ExternalLink className="h-3 w-3" aria-hidden />
                      </a>
                      <button
                        type="button"
                        disabled={saving || used || !slot || editor.draft.length >= 4}
                        onClick={() => {
                          if (slot)
                            editor.change([
                              ...editor.draft,
                              {
                                asset: photo,
                                selection_token: photo.selection_token,
                                alt: photo.title
                                  .replace(/\.(jpe?g|png|webp)$/i, "")
                                  .replaceAll("_", " "),
                                section_id: slot.id,
                              },
                            ]);
                        }}
                        className="inline-flex items-center gap-1 rounded-lg border border-stone-300 px-2 py-1 text-xs font-semibold text-slate-800 disabled:opacity-40"
                      >
                        <Plus className="h-3 w-3" aria-hidden />
                        {used ? "Selected" : "Select"}
                      </button>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void editor.submit();
            }}
            className="space-y-4"
          >
            <fieldset disabled={saving} className="space-y-4">
              <legend className="mb-3 text-sm font-semibold text-slate-800">
                In this article · {editor.draft.length}/4
              </legend>
              {editor.draft.map((item, index) => (
                <div
                  key={item.id ?? item.asset.source_id}
                  className="rounded-xl border border-stone-200 bg-stone-50 p-4"
                >
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <p className="min-w-0 truncate text-sm font-medium text-slate-800">
                      {item.asset.title}
                    </p>
                    <button
                      type="button"
                      aria-label={`Remove photo ${index + 1}`}
                      onClick={() =>
                        editor.change(editor.draft.filter((_, i) => i !== index))
                      }
                      className="shrink-0 rounded-lg p-2 text-slate-500 hover:bg-rose-50 hover:text-rose-700"
                    >
                      <Trash2 className="h-4 w-4" aria-hidden />
                    </button>
                  </div>
                  <label className="block text-xs font-medium text-slate-600">
                    Position
                    <select
                      value={item.section_id ?? "cover"}
                      className={field}
                      onChange={(event) =>
                        editor.change(
                          editor.draft.map((entry, i) =>
                            i === index
                              ? {
                                  ...entry,
                                  section_id:
                                    event.target.value === "cover"
                                      ? null
                                      : event.target.value,
                                }
                              : entry,
                          ),
                        )
                      }
                    >
                      {positions.map((position) => (
                        <option
                          key={position.id ?? "cover"}
                          value={position.id ?? "cover"}
                          disabled={editor.draft.some(
                            (entry, i) => i !== index && entry.section_id === position.id,
                          )}
                        >
                          {position.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="mt-3 block text-xs font-medium text-slate-600">
                    Alt text · describe what the reader needs to know
                    <input
                      required
                      maxLength={300}
                      value={item.alt}
                      className={field}
                      onChange={(event) =>
                        editor.change(
                          editor.draft.map((entry, i) =>
                            i === index ? { ...entry, alt: event.target.value } : entry,
                          ),
                        )
                      }
                    />
                  </label>
                  <p className="mt-2 text-[11px] text-slate-500">
                    Credit retained: {item.asset.creator} · {item.asset.license_name}
                  </p>
                </div>
              ))}
              <p className="text-xs text-slate-500">
                Review the suggested alt text. Exports link to the hosted images;
                full-resolution originals are available on each file page.
              </p>
              <div className="flex justify-end gap-2 border-t border-stone-200 pt-4">
                <button
                  type="button"
                  onClick={editor.cancel}
                  className="rounded-lg border border-stone-300 px-4 py-2 text-sm text-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!editor.dirty || saving}
                  className="inline-flex items-center gap-2 rounded-lg bg-[#17252b] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                >
                  {saving && <Spinner />}
                  {saving ? "Saving…" : "Save photos"}
                </button>
              </div>
            </fieldset>
          </form>
        </>
      )}
      {editor.confirmCancel && (
        <DiscardChangesDialog onKeep={editor.keep} onDiscard={editor.discard} />
      )}
    </div>
  );
}
