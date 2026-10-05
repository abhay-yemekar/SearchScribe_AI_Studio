"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { CopyPlus, Download, Menu, Sparkles } from "lucide-react";

import Tabs from "@/components/shared/Tabs";
import { ArticleSkeleton, ErrorBanner, Spinner } from "@/components/shared/States";
import ArticleSidebar from "@/features/articles/ArticleSidebar";
import ArticleEditor from "@/features/articles/ArticleEditor";
import SeoPanel from "@/features/articles/SeoPanel";
import HtmlPreview from "@/features/articles/HtmlPreview";
import VersionsPanel from "@/features/articles/VersionsPanel";
import { useSession } from "@/features/auth/useSession";
import {
  deleteArticle,
  duplicateArticle,
  fetchRewriteStyles,
  generateArticle,
  getArticle,
  listArticles,
  listVersions,
  restoreVersion,
  rewriteArticle,
  saveArticle,
} from "@/lib/api/articles";
import type { ArticleContent, Seo } from "@/lib/api/schemas";

export default function DashboardPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { token, user, bootstrapping, logout } = useSession();

  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState("article");
  const [style, setStyle] = useState("genz");
  const [actionError, setActionError] = useState<string | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const queryInputRef = useRef<HTMLInputElement>(null);
  const navButtonRef = useRef<HTMLButtonElement>(null);

  // Redirect if the session bootstrap comes back empty-handed.
  useEffect(() => {
    if (!bootstrapping && !token) router.replace("/");
  }, [bootstrapping, token, router]);

  useEffect(() => {
    if (!mobileNavOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMobileNavOpen(false);
        navButtonRef.current?.focus();
      }
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [mobileNavOpen]);

  const articlesQuery = useInfiniteQuery({
    queryKey: ["articles"],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) => listArticles(20, pageParam),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled: !!token,
  });

  const articles = articlesQuery.data?.pages.flatMap((page) => page.items) ?? [];

  const selectedQuery = useQuery({
    queryKey: ["article", selectedId],
    queryFn: () => getArticle(selectedId as number),
    enabled: !!token && selectedId !== null,
  });

  const versionsQuery = useQuery({
    queryKey: ["versions", selectedId],
    queryFn: () => listVersions(selectedId as number),
    enabled: !!token && selectedId !== null,
  });

  const stylesQuery = useQuery({
    queryKey: ["rewrite-styles"],
    queryFn: fetchRewriteStyles,
    enabled: !!token,
    staleTime: Infinity,
  });

  const invalidateSelected = useCallback(() => {
    if (selectedId !== null) {
      void queryClient.invalidateQueries({ queryKey: ["article", selectedId] });
      void queryClient.invalidateQueries({ queryKey: ["versions", selectedId] });
    }
    void queryClient.invalidateQueries({ queryKey: ["articles"] });
  }, [queryClient, selectedId]);

  const generate = useMutation({
    mutationFn: (topic: string) => generateArticle(topic),
    onSuccess: (detail) => {
      setActionError(null);
      setSelectedId(detail.id);
      setActiveTab("article");
      setQuery("");
      void queryClient.invalidateQueries({ queryKey: ["articles"] });
    },
    onError: (error) => setActionError((error as Error).message),
  });

  const rewrite = useMutation({
    mutationFn: () => rewriteArticle(selectedId as number, style),
    onSuccess: invalidateSelected,
    onError: (error) => setActionError((error as Error).message),
  });

  const remove = useMutation({
    mutationFn: (id: number) => deleteArticle(id),
    onSuccess: (_data, id) => {
      if (id === selectedId) setSelectedId(null);
      void queryClient.invalidateQueries({ queryKey: ["articles"] });
    },
    onError: (error) => setActionError((error as Error).message),
  });

  const duplicate = useMutation({
    mutationFn: (id: number) => duplicateArticle(id),
    onSuccess: (detail) => {
      setSelectedId(detail.id);
      void queryClient.invalidateQueries({ queryKey: ["articles"] });
    },
    onError: (error) => setActionError((error as Error).message),
  });

  const restore = useMutation({
    mutationFn: (version: number) => restoreVersion(selectedId as number, version),
    onSuccess: invalidateSelected,
    onError: (error) => setActionError((error as Error).message),
  });

  const save = useMutation({
    mutationFn: ({ content, seo }: { content: ArticleContent; seo: Seo }) => {
      if (!detail) throw new Error("Article is not loaded.");
      return saveArticle(detail.id, detail.current_version, content, seo);
    },
    onSuccess: (updated) => {
      setActionError(null);
      queryClient.setQueryData(["article", updated.id], updated);
      invalidateSelected();
    },
    onError: (error) => setActionError((error as Error).message),
  });

  const detail = selectedQuery.data;

  const downloadHtml = useCallback(() => {
    if (!detail) return;
    const blob = new Blob([detail.html], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${detail.title.replace(/[^\w\- ]+/g, "").slice(0, 60) || "article"}.html`;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }, [detail]);

  const handleGenerate = () => {
    const topic = query.trim();
    if (topic.length < 3) {
      setActionError("Enter a topic (at least 3 characters).");
      return;
    }
    setActionError(null);
    generate.mutate(topic);
  };

  if (bootstrapping) {
    return (
      <div className="flex h-screen items-center justify-center gap-3 bg-slate-950 text-slate-400">
        <Spinner className="h-6 w-6" /> Restoring session…
      </div>
    );
  }

  return (
    <div className="relative flex h-dvh overflow-hidden bg-slate-950 text-white">
      {mobileNavOpen ? (
        <button
          type="button"
          aria-label="Close article navigation"
          onClick={() => {
            setMobileNavOpen(false);
            navButtonRef.current?.focus();
          }}
          className="fixed inset-0 z-30 bg-black/70 md:hidden"
        />
      ) : null}
      <ArticleSidebar
        articles={articles}
        loading={articlesQuery.isLoading}
        loadingMore={articlesQuery.isFetchingNextPage}
        hasMore={articlesQuery.hasNextPage}
        selectedId={selectedId}
        deletingId={remove.isPending ? selectedId : null}
        onSelect={(id) => {
          setSelectedId(id);
          setActiveTab("article");
          setMobileNavOpen(false);
        }}
        onNewArticle={() => {
          setSelectedId(null);
          setActionError(null);
          setMobileNavOpen(false);
          queryInputRef.current?.focus();
        }}
        onLoadMore={() => {
          void articlesQuery.fetchNextPage();
        }}
        onDelete={(id) => remove.mutate(id)}
        mobileOpen={mobileNavOpen}
        onClose={() => {
          setMobileNavOpen(false);
          navButtonRef.current?.focus();
        }}
      />

      <main className="flex min-h-0 min-w-0 flex-1 flex-col gap-4 overflow-y-auto p-4 sm:p-6">
        <header className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2">
            <button
              ref={navButtonRef}
              type="button"
              aria-label="Open article navigation"
              aria-controls="article-sidebar"
              aria-expanded={mobileNavOpen}
              onClick={() => setMobileNavOpen(true)}
              className="rounded border border-slate-700 p-2 text-slate-200 hover:bg-slate-800 md:hidden"
            >
              <Menu aria-hidden className="h-5 w-5" />
            </button>
            <h1 className="truncate text-lg font-bold tracking-tight sm:text-xl">
              Article workspace
            </h1>
          </div>
          <div className="flex items-center gap-3 text-sm text-slate-300">
            {user ? <span className="hidden sm:inline">Hi, {user.name}</span> : null}
            <button
              type="button"
              onClick={() => void logout()}
              className="rounded border border-slate-600 px-3 py-1.5 transition-colors hover:bg-slate-800"
            >
              Logout
            </button>
          </div>
        </header>

        {/* Query + generate */}
        <div>
          <label htmlFor="topic" className="mb-1 block text-sm text-slate-300">
            Topic / search query
          </label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              id="topic"
              maxLength={500}
              ref={queryInputRef}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                  event.preventDefault();
                  handleGenerate();
                }
              }}
              placeholder="e.g. Things to do in Pune"
              className="w-full rounded border border-slate-700 bg-slate-900 p-2 text-sm outline-none transition-colors focus:border-blue-500"
            />
            <button
              type="button"
              onClick={handleGenerate}
              disabled={generate.isPending}
              className="flex shrink-0 items-center justify-center gap-2 rounded bg-blue-600 px-4 py-2 text-sm font-medium transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {generate.isPending ? (
                <Spinner />
              ) : (
                <Sparkles aria-hidden className="h-4 w-4" />
              )}
              {generate.isPending ? "Generating…" : "Generate"}
            </button>
          </div>
          <p className="mt-1 text-[11px] text-slate-500">
            Tip: press <kbd className="rounded bg-slate-800 px-1">Ctrl</kbd>+
            <kbd className="rounded bg-slate-800 px-1">Enter</kbd> to generate.
          </p>
        </div>

        {actionError ? <ErrorBanner message={actionError} /> : null}

        {/* Workspace */}
        {selectedId === null ? (
          <div className="flex min-h-80 flex-1 items-center justify-center rounded-xl border border-slate-700 bg-slate-900/50 px-4 text-center text-sm text-slate-400">
            {generate.isPending ? (
              <div className="w-full max-w-2xl space-y-6 p-8">
                <p className="text-center text-sm text-slate-300">
                  Writing your article…
                </p>
                <ArticleSkeleton />
              </div>
            ) : (
              "Generate an article or pick one from the sidebar."
            )}
          </div>
        ) : selectedQuery.isLoading ? (
          <div className="flex-1 space-y-3 p-4">
            <ArticleSkeleton />
          </div>
        ) : selectedQuery.isError ? (
          <ErrorBanner message={(selectedQuery.error as Error).message} />
        ) : detail ? (
          <div className="flex min-h-[32rem] flex-1 flex-col gap-3">
            {/* Title + actions */}
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="w-full min-w-0 px-1 py-1 text-lg font-semibold sm:flex-1 sm:truncate">
                {detail.title}
              </h2>
              <button
                type="button"
                onClick={() => duplicate.mutate(detail.id)}
                aria-label="Duplicate article"
                title="Duplicate article"
                className="rounded border border-slate-600 p-2 transition-colors hover:bg-slate-800"
              >
                <CopyPlus aria-hidden className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={downloadHtml}
                aria-label="Download HTML"
                title="Download HTML"
                className="rounded border border-slate-600 p-2 transition-colors hover:bg-slate-800"
              >
                <Download aria-hidden className="h-4 w-4" />
              </button>

              {/* Rewrite controls */}
              <div className="flex max-w-full flex-wrap items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-2 py-1">
                <label htmlFor="style" className="text-xs text-slate-400">
                  Rewrite as
                </label>
                <select
                  id="style"
                  value={style}
                  onChange={(event) => setStyle(event.target.value)}
                  className="rounded bg-slate-800 px-2 py-1 text-xs outline-none"
                >
                  {(stylesQuery.data?.styles ?? [{ key: "genz", label: "Gen Z" }]).map(
                    (s) => (
                      <option key={s.key} value={s.key}>
                        {s.label}
                      </option>
                    ),
                  )}
                </select>
                <button
                  type="button"
                  onClick={() => rewrite.mutate()}
                  disabled={rewrite.isPending}
                  className="flex items-center gap-1.5 rounded bg-rose-600 px-3 py-1 text-xs font-medium transition-colors hover:bg-rose-700 disabled:opacity-60"
                >
                  {rewrite.isPending ? <Spinner className="h-3.5 w-3.5" /> : null}
                  {rewrite.isPending ? "Rewriting…" : "Rewrite"}
                </button>
              </div>
            </div>

            <Tabs
              active={activeTab}
              onChange={setActiveTab}
              tabs={[
                {
                  key: "article",
                  label: "Article",
                  content: (
                    <ArticleEditor
                      key={`article-${detail.id}-${detail.current_version}`}
                      content={detail.content}
                      saving={save.isPending}
                      onSave={(content) => {
                        if (!detail.seo) {
                          setActionError("SEO metadata is required before saving.");
                          return;
                        }
                        save.mutate({ content, seo: detail.seo });
                      }}
                    />
                  ),
                },
                {
                  key: "seo",
                  label: "SEO Metadata",
                  content: (
                    <SeoPanel
                      key={`seo-${detail.id}-${detail.current_version}`}
                      seo={detail.seo}
                      saving={save.isPending}
                      onSave={(seo) => save.mutate({ content: detail.content, seo })}
                    />
                  ),
                },
                {
                  key: "preview",
                  label: "HTML Preview",
                  content: (
                    <HtmlPreview
                      html={detail.html}
                      title={detail.title}
                      onDownload={downloadHtml}
                    />
                  ),
                },
                {
                  key: "versions",
                  label: "Versions",
                  content: (
                    <VersionsPanel
                      versions={versionsQuery.data?.items ?? []}
                      currentVersion={detail.current_version}
                      restoring={restore.isPending}
                      onRestore={(version) => restore.mutate(version)}
                    />
                  ),
                },
              ]}
            />
          </div>
        ) : null}
      </main>
    </div>
  );
}
