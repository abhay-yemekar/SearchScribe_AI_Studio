"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { CopyPlus, Download, Sparkles } from "lucide-react";

import Tabs from "@/components/shared/Tabs";
import { ArticleSkeleton, ErrorBanner, Spinner } from "@/components/shared/States";
import ArticleSidebar from "@/features/articles/ArticleSidebar";
import ArticleView from "@/features/articles/ArticleView";
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
  renameArticle,
  restoreVersion,
  rewriteArticle,
} from "@/lib/api/articles";

export default function DashboardPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { token, user, bootstrapping, logout } = useSession();

  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState("article");
  const [style, setStyle] = useState("genz");
  const [actionError, setActionError] = useState<string | null>(null);
  const queryInputRef = useRef<HTMLInputElement>(null);

  // Redirect if the session bootstrap comes back empty-handed.
  useEffect(() => {
    if (!bootstrapping && !token) router.replace("/");
  }, [bootstrapping, token, router]);

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

  const rename = useMutation({
    mutationFn: (title: string) => renameArticle(selectedId as number, title),
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

  const copyMarkdown = useCallback(() => {
    if (detail) void navigator.clipboard.writeText(detail.markdown);
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
    <div className="flex h-screen bg-slate-950 text-white">
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
        }}
        onNewArticle={() => {
          setSelectedId(null);
          setActionError(null);
          queryInputRef.current?.focus();
        }}
        onLoadMore={() => {
          void articlesQuery.fetchNextPage();
        }}
        onDelete={(id) => remove.mutate(id)}
      />

      <main className="flex min-w-0 flex-1 flex-col gap-4 p-6">
        <header className="flex items-center justify-between">
          <h1 className="text-xl font-bold tracking-tight">Article workspace</h1>
          <div className="flex items-center gap-3 text-sm text-slate-300">
            {user ? <span>Hi, {user.name}</span> : null}
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
          <div className="flex gap-2">
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
              className="flex shrink-0 items-center gap-2 rounded bg-blue-600 px-4 py-2 text-sm font-medium transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
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
          <div className="flex flex-1 items-center justify-center rounded-xl border border-slate-700 bg-slate-900/50 text-sm text-slate-400">
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
          <div className="flex min-h-0 flex-1 flex-col gap-3">
            {/* Title + actions */}
            <div className="flex flex-wrap items-center gap-2">
              <input
                aria-label="Article title"
                defaultValue={detail.title}
                key={detail.id}
                onBlur={(event) => {
                  const value = event.target.value.trim();
                  if (value && value !== detail.title) {
                    rename.mutate(value);
                  }
                }}
                className="min-w-0 flex-1 rounded border border-transparent bg-transparent px-2 py-1 text-lg font-semibold outline-none transition-colors hover:border-slate-700 focus:border-blue-500"
              />
              <button
                type="button"
                onClick={() => duplicate.mutate(detail.id)}
                title="Duplicate article"
                className="rounded border border-slate-600 p-2 transition-colors hover:bg-slate-800"
              >
                <CopyPlus aria-hidden className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={downloadHtml}
                title="Download HTML"
                className="rounded border border-slate-600 p-2 transition-colors hover:bg-slate-800"
              >
                <Download aria-hidden className="h-4 w-4" />
              </button>

              {/* Rewrite controls */}
              <div className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-2 py-1">
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
                    <ArticleView markdown={detail.markdown} onCopy={copyMarkdown} />
                  ),
                },
                {
                  key: "seo",
                  label: "SEO Metadata",
                  content: <SeoPanel seo={detail.seo} />,
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
