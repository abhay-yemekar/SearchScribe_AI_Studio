"use client";

import { FilePlus2, Trash2 } from "lucide-react";
import { EmptyState, Spinner } from "@/components/shared/States";
import type { ArticleListItem } from "@/lib/api/schemas";

export default function ArticleSidebar({
  articles,
  loading,
  loadingMore,
  hasMore,
  selectedId,
  deletingId,
  onSelect,
  onNewArticle,
  onLoadMore,
  onDelete,
}: {
  articles: ArticleListItem[];
  loading: boolean;
  loadingMore: boolean;
  hasMore: boolean;
  selectedId: number | null;
  deletingId: number | null;
  onSelect: (id: number) => void;
  onNewArticle: () => void;
  onLoadMore: () => void;
  onDelete: (id: number) => void;
}) {
  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-slate-800 bg-slate-900/60 p-4">
      <h2 className="mb-4 flex items-center gap-2 text-base font-semibold">
        SearchScribe
        <span className="rounded bg-blue-600/20 px-1.5 py-0.5 text-[10px] font-medium text-blue-300">
          AI Studio
        </span>
      </h2>

      <button
        type="button"
        onClick={onNewArticle}
        className="mb-2 flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 py-2 text-sm font-medium transition-colors hover:bg-blue-700"
      >
        <FilePlus2 aria-hidden className="h-4 w-4" /> New article
      </button>

      <h3 className="mb-2 mt-4 text-xs font-semibold uppercase tracking-wide text-slate-400">
        Articles
      </h3>

      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        {loading ? (
          <div className="flex items-center gap-2 p-2 text-xs text-slate-500">
            <Spinner className="h-3.5 w-3.5" /> Loading articles…
          </div>
        ) : articles.length === 0 ? (
          <EmptyState
            title="No articles yet"
            hint="Enter a topic above and hit Generate to create your first one."
          />
        ) : (
          <ul className="space-y-1">
            {articles.map((article) => {
              const isSelected = article.id === selectedId;
              return (
                <li key={article.id} className="group relative">
                  <button
                    type="button"
                    onClick={() => onSelect(article.id)}
                    aria-current={isSelected ? "true" : undefined}
                    className={`w-full rounded-md px-2 py-2 text-left transition-colors ${
                      isSelected ? "bg-slate-800" : "hover:bg-slate-800/60"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm text-slate-100">
                        {article.title}
                      </span>
                      <span className="shrink-0 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400">
                        v{article.current_version}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="truncate text-xs text-slate-500">
                        {article.query}
                      </span>
                      <span className="shrink-0 text-[10px] text-slate-500">
                        {new Date(article.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete ${article.title}`}
                    disabled={deletingId === article.id}
                    onClick={() => onDelete(article.id)}
                    className="absolute right-1.5 top-1.5 hidden rounded p-1 text-slate-500 transition-colors hover:bg-rose-900/60 hover:text-rose-300 group-hover:block"
                  >
                    {deletingId === article.id ? (
                      <Spinner className="h-3.5 w-3.5" />
                    ) : (
                      <Trash2 aria-hidden className="h-3.5 w-3.5" />
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {hasMore && !loading ? (
        <button
          type="button"
          onClick={onLoadMore}
          disabled={loadingMore}
          className="mt-2 flex w-full items-center justify-center gap-2 rounded border border-slate-700 py-1.5 text-xs text-slate-300 transition-colors hover:bg-slate-800 disabled:opacity-60"
        >
          {loadingMore ? <Spinner className="h-3.5 w-3.5" /> : null}
          {loadingMore ? "Loading…" : "Load more"}
        </button>
      ) : null}
    </aside>
  );
}
