"use client";

import { useState } from "react";
import { Plus, Save, Trash2 } from "lucide-react";

import { Spinner } from "@/components/shared/States";
import type { ArticleContent } from "@/lib/api/schemas";

const field =
  "w-full rounded-lg border border-stone-300 bg-stone-50 px-3 py-2 text-sm text-slate-900 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100";

function copyContent(content: ArticleContent): ArticleContent {
  return structuredClone(content);
}

function wordCount(content: ArticleContent): number {
  const text = [
    content.title,
    content.introduction,
    ...content.sections.flatMap((section) => [
      section.heading,
      ...section.paragraphs,
      ...section.bullets,
    ]),
    content.conclusion,
  ].join(" ");
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

export default function ArticleEditor({
  content,
  saving,
  onSave,
}: {
  content: ArticleContent;
  saving: boolean;
  onSave: (content: ArticleContent) => void;
}) {
  const [draft, setDraft] = useState(() => copyContent(content));
  const [editing, setEditing] = useState(false);

  if (!editing) {
    return (
      <div className="mx-auto max-w-3xl space-y-7 font-serif text-base leading-8 text-slate-700">
        <div className="flex items-center justify-between border-b border-stone-200 pb-4 font-sans">
          <span className="text-xs font-medium uppercase tracking-wider text-slate-500">
            {wordCount(content)} words
          </span>
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="rounded-lg bg-teal-700 px-3 py-1.5 text-sm font-semibold text-white hover:bg-teal-800"
          >
            Edit article
          </button>
        </div>
        <p>{content.introduction}</p>
        {content.sections.map((section) => (
          <section key={section.id} className="space-y-3">
            <h2 className="pt-2 font-serif text-2xl font-semibold leading-tight text-slate-900">
              {section.heading}
            </h2>
            {section.paragraphs.map((paragraph, index) => (
              <p key={index}>{paragraph}</p>
            ))}
            {section.bullets.length ? (
              <ul className="list-disc space-y-1 pl-5">
                {section.bullets.map((bullet, index) => (
                  <li key={index}>{bullet}</li>
                ))}
              </ul>
            ) : null}
          </section>
        ))}
        <h2 className="pt-2 font-serif text-2xl font-semibold text-slate-900">
          Conclusion
        </h2>
        <p>{content.conclusion}</p>
      </div>
    );
  }

  const changeSection = (
    index: number,
    patch: Partial<ArticleContent["sections"][number]>,
  ) => {
    setDraft((current) => ({
      ...current,
      sections: current.sections.map((section, i) =>
        i === index ? { ...section, ...patch } : section,
      ),
    }));
  };

  return (
    <form
      className="mx-auto max-w-3xl space-y-5"
      onSubmit={(event) => {
        event.preventDefault();
        onSave(draft);
      }}
    >
      <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
        Title
        <input
          className={`${field} mt-1`}
          value={draft.title}
          maxLength={200}
          required
          onChange={(event) => setDraft({ ...draft, title: event.target.value })}
        />
      </label>
      <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
        Introduction
        <textarea
          className={`${field} mt-1 min-h-28`}
          value={draft.introduction}
          required
          onChange={(event) => setDraft({ ...draft, introduction: event.target.value })}
        />
      </label>
      {draft.sections.map((section, index) => (
        <fieldset
          key={section.id}
          className="space-y-3 rounded-xl border border-stone-200 bg-stone-50/50 p-4"
        >
          <div className="flex items-center justify-between">
            <legend className="text-xs font-semibold uppercase tracking-wide text-slate-600">
              Section {index + 1}
            </legend>
            {draft.sections.length > 1 ? (
              <button
                type="button"
                aria-label={`Remove section ${index + 1}`}
                onClick={() =>
                  setDraft({
                    ...draft,
                    sections: draft.sections.filter((_, i) => i !== index),
                  })
                }
                className="rounded p-1 text-slate-500 hover:bg-rose-50 hover:text-rose-700"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            ) : null}
          </div>
          <input
            aria-label={`Section ${index + 1} heading`}
            className={field}
            value={section.heading}
            required
            onChange={(event) => changeSection(index, { heading: event.target.value })}
          />
          <textarea
            aria-label={`Section ${index + 1} paragraphs`}
            className={`${field} min-h-32`}
            value={section.paragraphs.join("\n\n")}
            onChange={(event) =>
              changeSection(index, {
                paragraphs: event.target.value.split(/\n\s*\n/).filter(Boolean),
              })
            }
          />
          <textarea
            aria-label={`Section ${index + 1} bullets`}
            className={`${field} min-h-20`}
            placeholder="One bullet per line"
            value={section.bullets.join("\n")}
            onChange={(event) =>
              changeSection(index, {
                bullets: event.target.value
                  .split("\n")
                  .map((item) => item.trim())
                  .filter(Boolean),
              })
            }
          />
        </fieldset>
      ))}
      <button
        type="button"
        onClick={() =>
          setDraft({
            ...draft,
            sections: [
              ...draft.sections,
              {
                id: crypto.randomUUID().replaceAll("-", ""),
                heading: "New section",
                paragraphs: ["Start writing…"],
                bullets: [],
              },
            ],
          })
        }
        className="flex items-center gap-2 rounded-lg border border-stone-300 px-3 py-2 text-sm text-slate-700 hover:border-teal-600 hover:text-teal-800"
      >
        <Plus className="h-4 w-4" /> Add section
      </button>
      <label className="block text-xs font-semibold uppercase tracking-wide text-slate-600">
        Conclusion
        <textarea
          className={`${field} mt-1 min-h-28`}
          value={draft.conclusion}
          required
          onChange={(event) => setDraft({ ...draft, conclusion: event.target.value })}
        />
      </label>
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={() => {
            setDraft(copyContent(content));
            setEditing(false);
          }}
          className="rounded-lg border border-stone-300 px-4 py-2 text-sm text-slate-700 hover:bg-stone-50"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={saving}
          className="flex items-center gap-2 rounded-lg bg-teal-700 px-4 py-2 text-sm font-medium text-white hover:bg-teal-800 disabled:opacity-60"
        >
          {saving ? <Spinner /> : <Save className="h-4 w-4" />}
          {saving ? "Saving…" : "Save version"}
        </button>
      </div>
    </form>
  );
}
