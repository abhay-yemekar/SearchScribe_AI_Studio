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
      <div className="flex h-screen items-center justify-center gap-3 bg-stone-50 text-slate-600">
        <Spinner className="h-6 w-6" /> Restoring session…
      </div>
    );
  }

  return (
    <div className="relative flex h-dvh overflow-hidden bg-[#f5f3ee] text-slate-900">
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

      <main className="flex min-h-0 min-w-0 flex-1 flex-col gap-6 overflow-y-auto px-4 py-5 sm:px-8 sm:py-8 lg:px-12">
        <header className="flex items-center justify-between gap-3 border-b border-stone-200 pb-5">
          <div className="flex min-w-0 items-center gap-2">
            <button
              ref={navButtonRef}
              type="button"
              aria-label="Open article navigation"
              aria-controls="article-sidebar"
              aria-expanded={mobileNavOpen}
              onClick={() => setMobileNavOpen(true)}
              className="rounded-lg border border-stone-300 p-2 text-slate-700 hover:bg-white md:hidden"
            >
              <Menu aria-hidden className="h-5 w-5" />
            </button>
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-teal-700">
                Your writing desk
              </p>
              <h1 className="truncate font-serif text-2xl font-semibold tracking-tight sm:text-3xl">
                Article workspace
              </h1>
            </div>
          </div>
          <div className="flex items-center gap-3 text-sm text-slate-600">
            {user ? <span className="hidden sm:inline">Hi, {user.name}</span> : null}
            <button
              type="button"
              onClick={() => void logout()}
              className="rounded-lg border border-stone-300 bg-white px-3 py-1.5 transition-colors hover:border-teal-600 hover:text-teal-800"
            >
              Logout
            </button>
          </div>
        </header>

        {/* Query + generate */}
        <div className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm sm:p-6">
          <label
            htmlFor="topic"
            className="mb-2 block text-sm font-semibold text-slate-800"
          >
            What would you like to write about?
          </label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              id="topic"
              aria-label="Topic / search query"
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
              className="w-full rounded-xl border border-stone-300 bg-stone-50 px-4 py-3 text-sm text-slate-900 outline-none transition-colors placeholder:text-slate-400 focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
            />
            <button
              type="button"
              onClick={handleGenerate}
              disabled={generate.isPending}
              className="flex shrink-0 items-center justify-center gap-2 rounded-xl bg-teal-700 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {generate.isPending ? (
                <Spinner />
              ) : (
                <Sparkles aria-hidden className="h-4 w-4" />
              )}
              {generate.isPending ? "Generating…" : "Generate"}
            </button>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Tip: press <kbd className="rounded bg-stone-100 px-1">Ctrl</kbd>+
            <kbd className="rounded bg-stone-100 px-1">Enter</kbd> to generate.
          </p>
        </div>

        {actionError ? <ErrorBanner message={actionError} /> : null}

        {/* Workspace */}
        {selectedId === null ? (
          <div className="flex min-h-80 flex-1 items-center justify-center rounded-2xl border border-dashed border-stone-300 bg-white/70 px-4 text-center text-sm text-slate-500">
            {generate.isPending ? (
              <div className="w-full max-w-2xl space-y-6 p-8">
                <p className="text-center text-sm text-slate-600">
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
          <div className="flex min-h-[32rem] flex-1 flex-col gap-4">
            {/* Title + actions */}
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="w-full min-w-0 px-1 py-1 font-serif text-2xl font-semibold leading-tight sm:flex-1 sm:text-3xl">
                {detail.title}
              </h2>
              <button
                type="button"
                onClick={() => duplicate.mutate(detail.id)}
                aria-label="Duplicate article"
                title="Duplicate article"
                className="rounded-lg border border-stone-300 bg-white p-2 text-slate-600 transition-colors hover:border-teal-600 hover:text-teal-800"
              >
                <CopyPlus aria-hidden className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={downloadHtml}
                aria-label="Download HTML"
                title="Download HTML"
                className="rounded-lg border border-stone-300 bg-white p-2 text-slate-600 transition-colors hover:border-teal-600 hover:text-teal-800"
              >
                <Download aria-hidden className="h-4 w-4" />
              </button>

              {/* Rewrite controls */}
              <div className="flex max-w-full flex-wrap items-center gap-2 rounded-lg border border-stone-300 bg-white px-2 py-1">
                <label htmlFor="style" className="text-xs text-slate-600">
                  Rewrite as
                </label>
                <select
                  id="style"
                  value={style}
                  onChange={(event) => setStyle(event.target.value)}
                  className="rounded bg-stone-100 px-2 py-1 text-xs text-slate-800 outline-none focus:ring-2 focus:ring-teal-600"
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
                  className="flex items-center gap-1.5 rounded bg-teal-700 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-teal-800 disabled:opacity-60"
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
