"use client";

import { History, RotateCcw } from "lucide-react";
import { Spinner } from "@/components/shared/States";
import type { VersionItem } from "@/lib/api/schemas";

const CHANGE_LABELS: Record<string, string> = {
  generation: "Generated",
  rewrite: "Rewrite",
  restore: "Restored",
  edit: "Edited",
};

export default function VersionsPanel({
  versions,
  currentVersion,
  restoring,
  onRestore,
}: {
  versions: VersionItem[];
  currentVersion: number;
  restoring: boolean;
  onRestore: (version: number) => void;
}) {
  if (versions.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-500">
        Versions will appear here as you rewrite or restore the article.
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-3">
      <p className="flex items-center gap-2 text-xs text-slate-600">
        <History aria-hidden className="h-4 w-4" />
        Restoring an old version creates a new version — history is never lost.
      </p>
      <ul className="space-y-2">
        {versions.map((version) => {
          const isCurrent = version.version === currentVersion;
          return (
            <li
              key={version.version}
              className={`flex items-center justify-between rounded-lg border p-3 ${
                isCurrent ? "border-teal-300 bg-teal-50" : "border-stone-200 bg-stone-50"
              }`}
            >
              <div>
                <p className="text-sm font-medium text-slate-800">
                  Version {version.version}{" "}
                  <span className="ml-1 text-xs font-normal text-slate-500">
                    ({CHANGE_LABELS[version.change_type] ?? version.change_type})
                  </span>
                </p>
                <p className="text-xs text-slate-500">
                  {version.word_count.toLocaleString()} words ·{" "}
                  {new Date(version.created_at).toLocaleString()}
                </p>
                <p className="mt-1 text-[11px] text-slate-500">
                  {version.complete_snapshot
                    ? "Content + SEO snapshot"
                    : "Legacy content snapshot"}
                </p>
              </div>
              {isCurrent ? (
                <span className="text-xs font-medium text-teal-800">Current</span>
              ) : (
                <button
                  type="button"
                  disabled={restoring}
                  onClick={() => onRestore(version.version)}
                  className="flex items-center gap-1.5 rounded border border-stone-300 bg-white px-2.5 py-1 text-xs text-slate-700 transition-colors hover:border-teal-600 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {restoring ? (
                    <Spinner className="h-3 w-3" />
                  ) : (
                    <RotateCcw aria-hidden className="h-3.5 w-3.5" />
                  )}
                  Restore
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
