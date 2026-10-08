"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { FilePlus2, Trash2, X } from "lucide-react";
import BrandLogo from "@/components/brand/BrandLogo";
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
  mobileOpen = false,
  onClose,
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
  mobileOpen?: boolean;
  onClose?: () => void;
}) {
  const sidebarRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (mobileOpen) closeButtonRef.current?.focus();
  }, [mobileOpen]);

  return (
    <aside
      ref={sidebarRef}
      id="article-sidebar"
      aria-label="Article navigation"
      role={mobileOpen ? "dialog" : undefined}
      aria-modal={mobileOpen ? true : undefined}
      onKeyDown={(event) => {
        if (!mobileOpen || event.key !== "Tab") return;
        const focusable = Array.from(
          sidebarRef.current?.querySelectorAll<HTMLElement>(
            "a[href], button:not([disabled])",
          ) ?? [],
        ).filter((button) => button.getClientRects().length > 0);
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }}
      className={`studio-sidebar ${mobileOpen ? "fixed inset-y-0 left-0 z-40 flex" : "hidden"} w-72 max-w-[85vw] shrink-0 flex-col border-r border-stone-200 bg-[#e9eced] p-5 text-[#17252b] shadow-2xl md:static md:z-auto md:flex md:max-w-none md:shadow-none`}
    >
      <div className="mb-4 flex items-center justify-between gap-2">
        <Link href="/" aria-label="SearchScribe home" className="rounded-sm">
          <BrandLogo className="text-[#17252b]" />
        </Link>
        <button
          ref={closeButtonRef}
          type="button"
          onClick={onClose}
          aria-label="Close article navigation"
          className="rounded p-2 text-slate-600 hover:bg-stone-100 md:hidden"
        >
          <X aria-hidden className="h-5 w-5" />
        </button>
      </div>

      <button
        type="button"
        onClick={onNewArticle}
        className="studio-primary-action mb-2 flex w-full items-center justify-center gap-2 rounded-lg bg-[#e0f06b] py-3 text-sm font-semibold text-[#17252b] transition-colors hover:bg-[#d3e458]"
      >
        <FilePlus2 aria-hidden className="h-4 w-4" /> New article
      </button>

      <h3 className="mb-2 mt-5 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
        Articles
      </h3>

      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        {loading ? (
          <div className="flex items-center gap-2 p-2 text-xs text-slate-600">
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
                      isSelected
                        ? "bg-white shadow-sm ring-1 ring-stone-200"
                        : "hover:bg-white/70"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium text-slate-800">
                        {article.title}
                      </span>
                      <span className="shrink-0 rounded bg-stone-200 px-1.5 py-0.5 text-[10px] text-slate-600">
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
                    className="absolute right-1.5 top-1.5 block rounded p-1 text-slate-500 transition-colors hover:bg-rose-100 hover:text-rose-700 md:hidden md:group-hover:block md:focus-visible:block"
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
          className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg border border-stone-300 bg-white py-1.5 text-xs text-slate-700 transition-colors hover:border-[#17252b] disabled:opacity-60"
        >
          {loadingMore ? <Spinner className="h-3.5 w-3.5" /> : null}
          {loadingMore ? "Loading…" : "Load more"}
        </button>
      ) : null}
    </aside>
  );
}
