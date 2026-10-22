"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  useInfiniteQuery,
  skipToken,
  useIsMutating,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { ArrowUpRight, CopyPlus, Menu, Sparkles } from "lucide-react";

import Tabs from "@/components/shared/Tabs";
import { ArticleSkeleton, ErrorBanner, Spinner } from "@/components/shared/States";
import ArticleSidebar from "@/features/articles/ArticleSidebar";
import ArticleEditor from "@/features/articles/ArticleEditor";
import SeoPanel from "@/features/articles/SeoPanel";
import HtmlPreview from "@/features/articles/HtmlPreview";
import VersionsPanel from "@/features/articles/VersionsPanel";
import ArticleExport from "@/features/articles/ArticleExport";
import ResearchPanel from "@/features/articles/ResearchPanel";
import PhotosPanel, { type PhotoDraft } from "@/features/articles/PhotosPanel";
import DiscardChangesDialog from "@/features/articles/DiscardChangesDialog";
import UndoToast from "@/features/articles/UndoToast";
import { draftIsDirty, type EditorDraft } from "@/features/articles/useEditorDraft";
import { useUndoableDelete } from "@/features/articles/useUndoableDelete";
import { downloadArticleFile } from "@/lib/article-export";
import { useSession } from "@/features/auth/useSession";
import SessionLoading from "@/features/auth/SessionLoading";
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
  saveArticlePhotos,
} from "@/lib/api/articles";
import type { ArticleContent, ArticleDetail, Seo } from "@/lib/api/schemas";
import { isApiError } from "@/lib/api/errors";
import { actionErrorMessage } from "@/features/articles/action-error";
import { useGenerationRecovery } from "@/features/articles/useGenerationRecovery";

type DraftSession =
  | {
      id: string;
      revision: number;
      kind: "article";
      base: ArticleDetail;
      editor: EditorDraft<ArticleContent>;
    }
  | {
      id: string;
      revision: number;
      kind: "seo";
      base: ArticleDetail;
      editor: EditorDraft<Seo | null>;
    }
  | {
      id: string;
      revision: number;
      kind: "photos";
      base: ArticleDetail;
      editor: EditorDraft<PhotoDraft[]>;
    };
type WorkspaceMemory = {
  selectedId: number | null;
  activeTab: string;
  draft: DraftSession | null;
  editorEpoch: number;
  actionError: string | null;
  clarification: string | null;
};

export default function DashboardPage() {
  const router = useRouter();
  const session = useSession();
  const { token, user, bootstrapping } = session;
  useEffect(() => {
    if (!bootstrapping && !token) router.replace("/login");
  }, [bootstrapping, token, router]);
  if (bootstrapping) {
    return <SessionLoading />;
  }
  return token && user ? <WritingWorkspace key={user.id} session={session} /> : null;
}

function WritingWorkspace({ session }: { session: ReturnType<typeof useSession> }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { token, user, logout } = session;
  const recovery = useGenerationRecovery(user!.id);
  const memoryKey = ["workspace-draft", user!.id];
  const memoryQuery = useQuery<WorkspaceMemory>({
    queryKey: memoryKey,
    queryFn: skipToken,
    enabled: false,
    gcTime: Infinity,
    initialData: {
      selectedId: null,
      activeTab: "article",
      draft: null,
      editorEpoch: 0,
      actionError: null,
      clarification: null,
    },
  });
  const memory = memoryQuery.data!;
  const remember = (
    patch:
      Partial<WorkspaceMemory> | ((current: WorkspaceMemory) => Partial<WorkspaceMemory>),
  ) => {
    queryClient.setQueryData<WorkspaceMemory>(memoryKey, (current) =>
      current
        ? { ...current, ...(typeof patch === "function" ? patch(current) : patch) }
        : current,
    );
  };
  // A route remount can restore drafts in this tab; logout/password changes clear QueryClient.
  const sharedPending =
    useIsMutating({ mutationKey: ["workspace-action", user!.id] }) > 0;

  const [query, setQuery] = useState("");
  const {
    selectedId,
    activeTab,
    draft: draftSession,
    editorEpoch,
    actionError,
    clarification,
  } = memory;
  const setActionError = (error: string | null) => remember({ actionError: error });
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const pendingAction = useRef<(() => void) | null>(null);
  const dirty = draftIsDirty<unknown>(draftSession?.editor);
  const setSelectedId = (id: number | null) => remember({ selectedId: id });
  const setActiveTab = (tab: string) => remember({ activeTab: tab });
  const clearDraft = () => {
    remember((current) => ({ draft: null, editorEpoch: current.editorEpoch + 1 }));
  };
  const [style, setStyle] = useState("genz");
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const queryInputRef = useRef<HTMLInputElement>(null);
  const navButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!mobileNavOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !confirmDiscard) {
        setMobileNavOpen(false);
        navButtonRef.current?.focus();
      }
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [mobileNavOpen, confirmDiscard]);

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
    mutationKey: ["workspace-action", user!.id, "generate"],
    mutationFn: (topic: string) => recovery.run((key) => generateArticle(topic, key)),
    onSuccess: (detail) => {
      setActionError(null);
      remember({ clarification: null });
      setSelectedId(detail.id);
      setActiveTab("article");
      setQuery("");
      void queryClient.invalidateQueries({ queryKey: ["articles"] });
    },
    onError: (error) => {
      if (isApiError(error) && error.code === "TOPIC_CLARIFICATION_REQUIRED") {
        remember({ actionError: null, clarification: error.message });
        queryInputRef.current?.focus();
      } else {
        setActionError(actionErrorMessage(error));
      }
    },
  });

  const rewrite = useMutation({
    mutationKey: ["workspace-action", user!.id, "rewrite"],
    mutationFn: () => recovery.run((key) => rewriteArticle(selectedId as number, style, key)),
    onSuccess: invalidateSelected,
    onError: (error) => setActionError(actionErrorMessage(error)),
  });

  const remove = useMutation({
    mutationKey: ["workspace-action", user!.id, "delete"],
    mutationFn: (id: number) => deleteArticle(id),
    onSuccess: (_data, id) => {
      if (id === selectedId) setSelectedId(null);
      void queryClient.invalidateQueries({ queryKey: ["articles"] });
    },
    onError: (error) => setActionError((error as Error).message),
  });
  const pendingDelete = useUndoableDelete({
    commit: (id) => remove.mutate(id),
    commitOnPageHide: (id) => {
      void deleteArticle(id, { keepalive: true })
        .then(() => queryClient.invalidateQueries({ queryKey: ["articles"] }))
        .catch(() => undefined); // Best effort; the article reappears if this fails.
    },
  });
  const visibleArticles = articles.filter(
    (article) => article.id !== pendingDelete.pending?.id,
  );

  const duplicate = useMutation({
    mutationKey: ["workspace-action", user!.id, "duplicate"],
    mutationFn: (id: number) => duplicateArticle(id),
    onSuccess: (detail) => {
      setSelectedId(detail.id);
      void queryClient.invalidateQueries({ queryKey: ["articles"] });
    },
    onError: (error) => setActionError((error as Error).message),
  });

  const restore = useMutation({
    mutationKey: ["workspace-action", user!.id, "restore"],
    mutationFn: ({ version, base }: { version: number; base: number }) =>
      restoreVersion(selectedId as number, version, base),
    onSuccess: () => {
      setActionError(null);
      invalidateSelected();
    },
    onError: (error) => {
      setActionError((error as Error).message);
      // A 409 means a newer version exists; show it so the restore can be retried.
      invalidateSelected();
    },
  });

  const save = useMutation({
    mutationKey: ["workspace-action", user!.id, "save"],
    mutationFn: ({
      base,
      content,
      seo,
    }: {
      base: ArticleDetail;
      content: ArticleContent;
      seo: Seo;
      owner: { id: string; revision: number };
    }) => {
      return saveArticle(base.id, base.current_version, content, seo);
    },
    onSuccess: (updated, variables) => {
      const current = queryClient.getQueryData<WorkspaceMemory>(memoryKey);
      if (!current) return; // A logout/password change cleared the private cache.
      setActionError(null);
      queryClient.setQueryData(["article", updated.id], updated);
      if (
        current.draft?.id === variables.owner.id &&
        current.draft.revision === variables.owner.revision
      )
        clearDraft();
      invalidateSelected();
    },
    onError: (error) => setActionError((error as Error).message),
  });

  const photoSave = useMutation({
    mutationKey: ["workspace-action", user!.id, "photos"],
    mutationFn: ({
      base,
      photos,
    }: {
      base: ArticleDetail;
      photos: PhotoDraft[];
      owner: { id: string; revision: number };
    }) =>
      saveArticlePhotos(
        base.id,
        base.current_version,
        photos.map(({ id, selection_token, alt, section_id }) => ({
          id,
          selection_token,
          alt,
          section_id,
        })),
      ),
    onSuccess: (updated, variables) => {
      const current = queryClient.getQueryData<WorkspaceMemory>(memoryKey);
      if (!current) return;
      setActionError(null);
      queryClient.setQueryData(["article", updated.id], updated);
      if (
        current.draft?.id === variables.owner.id &&
        current.draft.revision === variables.owner.revision
      )
        clearDraft();
      invalidateSelected();
    },
    onError: (error) => setActionError(actionErrorMessage(error)),
  });

  const detail = selectedQuery.data;
  const busy = sharedPending;
  const saving =
    useIsMutating({ mutationKey: ["workspace-action", user!.id, "save"] }) > 0;
  const requestAction = (action: () => void) => {
    if (queryClient.isMutating({ mutationKey: ["workspace-action", user!.id] })) return;
    const currentDraft = queryClient.getQueryData<WorkspaceMemory>(memoryKey)?.draft;
    const currentDirty = draftIsDirty<unknown>(currentDraft?.editor);
    if (currentDirty) {
      pendingAction.current = action;
      setConfirmDiscard(true);
    } else {
      clearDraft();
      action();
    }
  };
  const updateArticleDraft = (editor: EditorDraft<ArticleContent>) => {
    remember((current) => {
      const previous = current.draft?.kind === "article" ? current.draft : null;
      const next: DraftSession | null =
        editor.editing && detail
          ? {
              id: previous?.id ?? crypto.randomUUID(),
              revision: (previous?.revision ?? 0) + 1,
              kind: "article",
              base: previous?.base ?? structuredClone(detail),
              editor,
            }
          : null;
      return { draft: next };
    });
  };
  const updateSeoDraft = (editor: EditorDraft<Seo | null>) => {
    remember((current) => {
      const previous = current.draft?.kind === "seo" ? current.draft : null;
      const next: DraftSession | null =
        editor.editing && detail
          ? {
              id: previous?.id ?? crypto.randomUUID(),
              revision: (previous?.revision ?? 0) + 1,
              kind: "seo",
              base: previous?.base ?? structuredClone(detail),
              editor,
            }
          : null;
      return { draft: next };
    });
  };
  const updatePhotoDraft = (editor: EditorDraft<PhotoDraft[]>) => {
    remember((current) => {
      const previous = current.draft?.kind === "photos" ? current.draft : null;
      return {
        draft:
          editor.editing && detail
            ? {
                id: previous?.id ?? crypto.randomUUID(),
                revision: (previous?.revision ?? 0) + 1,
                kind: "photos",
                base: previous?.base ?? structuredClone(detail),
                editor,
              }
            : null,
      };
    });
  };

  const downloadHtml = useCallback(() => {
    if (!detail) return;
    if (!dirty && !busy) downloadArticleFile(detail.title, detail.html, "html");
  }, [detail, dirty, busy]);

  useEffect(() => {
    if (!dirty && !saving && !photoSave.isPending) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, saving, photoSave.isPending]);

  const handleGenerate = () => {
    const topic = query.trim();
    if (topic.length < 3) {
      setActionError("Enter a topic (at least 3 characters).");
      return;
    }
    requestAction(() => {
      setActionError(null);
      remember({ clarification: null });
      generate.mutate(topic);
    });
  };

  return (
    <div className="studio-shell relative flex h-dvh overflow-hidden bg-[#f4f5f1] text-[#17252b]">
      {confirmDiscard ? (
        <DiscardChangesDialog
          onKeep={() => {
            pendingAction.current = null;
            setConfirmDiscard(false);
          }}
          onDiscard={() => {
            const action = pendingAction.current;
            pendingAction.current = null;
            setConfirmDiscard(false);
            clearDraft();
            action?.();
          }}
        />
      ) : null}
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
      {pendingDelete.pending ? (
        <UndoToast
          key={pendingDelete.pending.id}
          message={`Deleted “${pendingDelete.pending.title}”.`}
          onUndo={() => {
            const restored = pendingDelete.undo();
            // Reopen it only if nothing else was opened in the meantime.
            if (restored?.wasOpen && selectedId === null) {
              setSelectedId(restored.id);
              setActiveTab("article");
            }
          }}
        />
      ) : null}
      <ArticleSidebar
        articles={visibleArticles}
        loading={articlesQuery.isLoading}
        loadingMore={articlesQuery.isFetchingNextPage}
        hasMore={articlesQuery.hasNextPage}
        selectedId={selectedId}
        deletingId={remove.isPending ? remove.variables : null}
        disabled={busy}
        onHomeNavigate={(event) => {
          event.preventDefault();
          requestAction(() => router.push("/"));
        }}
        onSelect={(id) => {
          if (id === selectedId) {
            setMobileNavOpen(false);
            return;
          }
          requestAction(() => {
            setSelectedId(id);
            setActiveTab("article");
            setMobileNavOpen(false);
          });
        }}
        onNewArticle={() => {
          requestAction(() => {
            setSelectedId(null);
            setActionError(null);
            remember({ clarification: null });
            setMobileNavOpen(false);
            queryInputRef.current?.focus();
          });
        }}
        onLoadMore={() => {
          void articlesQuery.fetchNextPage();
        }}
        onDelete={(id) => {
          const article = articles.find((item) => item.id === id);
          if (!article) return;
          const hide = () => {
            pendingDelete.schedule({
              id,
              title: article.title,
              wasOpen: id === selectedId,
            });
            if (id === selectedId) setSelectedId(null);
          };
          if (id === selectedId) requestAction(hide);
          else if (!busy) hide();
        }}
        mobileOpen={mobileNavOpen}
        onClose={() => {
          setMobileNavOpen(false);
          navButtonRef.current?.focus();
        }}
      />

      <main className="flex min-h-0 min-w-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5 lg:px-8">
        <header className="flex shrink-0 flex-col gap-3 border-b border-stone-200 pb-3 sm:flex-row sm:items-center sm:justify-between">
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
              <p
                className={`${selectedId !== null ? "sr-only" : ""} text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500`}
              >
                Your writing desk
              </p>
              <h1 className="truncate text-xl font-semibold tracking-tight sm:text-2xl">
                Article workspace
              </h1>
            </div>
          </div>
          <div className="flex items-center gap-3 text-sm text-slate-600">
            {user ? <span className="hidden sm:inline">Hi, {user.name}</span> : null}
            <Link
              href="/"
              onNavigate={(event) => {
                event.preventDefault();
                requestAction(() => router.push("/"));
              }}
              aria-disabled={busy}
              className="inline-flex items-center gap-1 hover:underline"
            >
              Website <ArrowUpRight aria-hidden className="h-3.5 w-3.5" />
            </Link>
            <Link
              href="/account"
              onNavigate={(event) => {
                event.preventDefault();
                requestAction(() => router.push("/account"));
              }}
              aria-disabled={busy}
              className="hover:underline"
            >
              Account
            </Link>
            <button
              type="button"
              onClick={() => requestAction(() => void logout())}
              disabled={busy}
              className="rounded-lg border border-stone-300 bg-white px-3 py-1.5 transition-colors hover:border-[#17252b]"
            >
              Logout
            </button>
          </div>
        </header>

        {/* Query + generate */}
        <div
          className={`studio-panel shrink-0 rounded-xl border border-stone-200 bg-white ${selectedId !== null ? "p-3" : "p-4 sm:p-6"}`}
        >
          <label
            htmlFor="topic"
            className={
              selectedId !== null
                ? "sr-only"
                : "mb-2 block text-sm font-semibold text-slate-800"
            }
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
              aria-describedby={clarification ? "topic-clarification" : undefined}
              onKeyDown={(event) => {
                if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                  event.preventDefault();
                  handleGenerate();
                }
              }}
              placeholder="e.g. Things to do in Pune"
              className="w-full rounded-lg border border-stone-300 bg-stone-50 px-4 py-3 text-sm text-[#17252b] outline-hidden transition-colors placeholder:text-slate-400 focus:border-[#17252b] focus:ring-2 focus:ring-[#17252b]/15"
            />
            <button
              type="button"
              onClick={handleGenerate}
              disabled={busy || !!recovery.pendingKey}
              className="studio-primary-action flex shrink-0 items-center justify-center gap-2 rounded-lg bg-[#e0f06b] px-5 py-3 text-sm font-semibold text-[#17252b] transition-colors hover:bg-[#d3e458] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {generate.isPending ? (
                <Spinner />
              ) : (
                <Sparkles aria-hidden className="h-4 w-4" />
              )}
              {generate.isPending ? "Generating…" : "Generate"}
            </button>
          </div>
          <p
            className={`${selectedId !== null ? "sr-only" : "mt-2"} text-xs text-slate-500`}
          >
            Tip: press <kbd className="rounded-sm bg-stone-100 px-1">Ctrl</kbd>+
            <kbd className="rounded-sm bg-stone-100 px-1">Enter</kbd> to generate.
          </p>
        </div>

        {clarification ? (
          <div
            id="topic-clarification"
            role="status"
            className="studio-panel rounded-xl border border-stone-300 bg-white px-4 py-3 text-sm text-slate-700"
          >
            <p className="font-semibold text-[#17252b]">One detail before we write</p>
            <p className="mt-1">{clarification}</p>
            <p className="mt-1 text-xs text-slate-500">
              Add this detail to your topic, then generate again.
            </p>
          </div>
        ) : null}
        {actionError ? <ErrorBanner message={actionError} /> : null}
        {(recovery.pendingKey || recovery.notice) && !sharedPending ? (
          <div role="status" className="studio-panel flex shrink-0 flex-wrap items-center justify-between gap-3 rounded-xl border border-stone-300 bg-white px-4 py-3 text-sm text-slate-700">
            <p className="max-w-2xl">
              {recovery.notice || "A previous generation request needs a status check. Recover its result before generating again."}
            </p>
            {recovery.pendingKey ? (
              <button
                type="button"
                disabled={recovery.checking}
                className="rounded-lg border border-stone-300 px-3 py-2 font-medium text-[#17252b] disabled:opacity-50"
                onClick={async () => {
                  const articleId = await recovery.check();
                  if (articleId) requestAction(() => {
                    setSelectedId(articleId);
                    setActiveTab("article");
                    setActionError(null);
                    void queryClient.invalidateQueries({ queryKey: ["articles"] });
                    void queryClient.invalidateQueries({ queryKey: ["article", articleId] });
                    void queryClient.invalidateQueries({ queryKey: ["versions", articleId] });
                  });
                }}
              >
                {recovery.checking ? "Checking…" : "Check previous request"}
              </button>
            ) : null}
          </div>
        ) : null}
        {dirty || saving ? (
          <p role="status" className="text-sm font-semibold text-teal-800">
            {saving ? "Saving changes…" : "Unsaved changes"}
          </p>
        ) : null}

        {/* Workspace */}
        {selectedId === null ? (
          <div className="studio-panel flex min-h-80 flex-auto shrink-0 items-center justify-center rounded-xl border border-stone-200 bg-white/70 px-6 py-12 text-sm text-slate-500">
            {generate.isPending ? (
              <div className="w-full max-w-2xl space-y-6 p-8">
                <p className="text-center text-sm text-slate-600">
                  Researching your topic and writing your draft…
                </p>
                <ArticleSkeleton />
              </div>
            ) : (
              <div className="w-full max-w-2xl">
                <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em]">
                  A blank page. A place to begin.
                </p>
                <h2 className="text-2xl font-semibold tracking-tight text-[#17252b]">
                  What will you write next?
                </h2>
                <p className="mt-3 leading-relaxed">
                  Enter a topic above to make a first draft, or open a saved article from
                  the sidebar. Every draft is yours to shape.
                </p>
                <ol className="mt-8 grid gap-5 border-t border-stone-200 pt-6 sm:grid-cols-3">
                  <li>
                    <span className="text-[11px] font-semibold">01 / START</span>
                    <p className="mt-2 font-semibold text-[#17252b]">Choose a topic</p>
                    <p className="mt-1 leading-relaxed">
                      Tell us what you want to write about.
                    </p>
                  </li>
                  <li>
                    <span className="text-[11px] font-semibold">02 / SHAPE</span>
                    <p className="mt-2 font-semibold text-[#17252b]">Make it your own</p>
                    <p className="mt-1 leading-relaxed">
                      Edit the draft and review its SEO details.
                    </p>
                  </li>
                  <li>
                    <span className="text-[11px] font-semibold">
                      03 / TAKE IT WITH YOU
                    </span>
                    <p className="mt-2 font-semibold text-[#17252b]">
                      Export your article
                    </p>
                    <p className="mt-1 leading-relaxed">
                      Download HTML or Markdown when you are ready.
                    </p>
                  </li>
                </ol>
              </div>
            )}
          </div>
        ) : selectedQuery.isLoading ? (
          <div className="flex-1 space-y-3 p-4">
            <ArticleSkeleton />
          </div>
        ) : selectedQuery.isError ? (
          <ErrorBanner message={(selectedQuery.error as Error).message} />
        ) : detail ? (
          <div className="flex min-h-128 flex-auto shrink-0 flex-col gap-3">
            {/* Title + actions */}
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="w-full min-w-0 py-1 text-xl font-semibold leading-tight tracking-tight sm:text-2xl sm:leading-8">
                {detail.title}
              </h2>
              <button
                type="button"
                onClick={() => requestAction(() => duplicate.mutate(detail.id))}
                disabled={busy}
                aria-label="Duplicate article"
                title="Duplicate article"
                className="rounded-lg border border-stone-300 bg-white p-2 text-slate-600 transition-colors hover:border-[#17252b] hover:text-[#17252b]"
              >
                <CopyPlus aria-hidden className="h-4 w-4" />
              </button>
              <ArticleExport
                title={detail.title}
                html={detail.html}
                markdown={detail.markdown}
                disabled={dirty || busy}
                disabledReason={
                  dirty
                    ? "Save or discard your changes before exporting."
                    : "Wait for the current action to finish before exporting."
                }
              />

              {/* Rewrite controls */}
              <div className="flex max-w-full flex-wrap items-center gap-2 rounded-lg border border-stone-300 bg-white px-2 py-1">
                <label htmlFor="style" className="text-xs text-slate-600">
                  Rewrite as
                </label>
                <select
                  id="style"
                  value={style}
                  onChange={(event) => setStyle(event.target.value)}
                  className="rounded-sm bg-stone-100 px-2 py-1 text-xs text-slate-800 outline-hidden focus:ring-2 focus:ring-[#17252b]"
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
                  onClick={() => requestAction(() => rewrite.mutate())}
                  disabled={busy || !!recovery.pendingKey}
                  className="flex items-center gap-1.5 rounded-sm bg-[#17252b] px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-[#293f48] disabled:opacity-60"
                >
                  {rewrite.isPending ? <Spinner className="h-3.5 w-3.5" /> : null}
                  {rewrite.isPending ? "Rewriting…" : "Rewrite"}
                </button>
              </div>
              <button
                type="button"
                onClick={() => requestAction(() => setActiveTab("sources"))}
                className="ml-auto rounded-full border border-stone-200 px-3 py-1 text-xs text-slate-600 hover:border-teal-600 hover:text-teal-800 focus-visible:outline-solid focus-visible:outline-2 focus-visible:outline-teal-700"
              >
                {detail.content.research?.status === "sources_retrieved"
                  ? `${detail.content.research.sources.length} sources`
                  : "Unresearched draft"}
              </button>
            </div>

            <Tabs
              active={activeTab}
              onChange={(tab) => {
                if (tab !== activeTab) requestAction(() => setActiveTab(tab));
              }}
              tabs={[
                {
                  key: "article",
                  label: "Article",
                  content: (
                    <ArticleEditor
                      key={`article-${detail.id}-${editorEpoch}`}
                      content={detail.content}
                      initialDraft={
                        draftSession?.kind === "article" ? draftSession.editor : undefined
                      }
                      onDraftChange={updateArticleDraft}
                      requestDiscard={requestAction}
                      saving={busy}
                      onSave={async (content) => {
                        const currentDraft =
                          queryClient.getQueryData<WorkspaceMemory>(memoryKey)?.draft;
                        if (
                          currentDraft?.kind !== "article" ||
                          queryClient.isMutating({
                            mutationKey: ["workspace-action", user!.id],
                          })
                        )
                          throw new Error("An article edit is required before saving.");
                        const base = currentDraft.base;
                        if (!base.seo)
                          throw new Error("SEO metadata is required before saving.");
                        await save.mutateAsync({
                          base,
                          content,
                          seo: base.seo,
                          owner: { id: currentDraft.id, revision: currentDraft.revision },
                        });
                      }}
                    />
                  ),
                },
                {
                  key: "seo",
                  label: "SEO Metadata",
                  content: (
                    <SeoPanel
                      key={`seo-${detail.id}-${editorEpoch}`}
                      seo={detail.seo}
                      initialDraft={
                        draftSession?.kind === "seo" ? draftSession.editor : undefined
                      }
                      onDraftChange={updateSeoDraft}
                      requestDiscard={requestAction}
                      saving={busy}
                      onSave={async (seo) => {
                        const currentDraft =
                          queryClient.getQueryData<WorkspaceMemory>(memoryKey)?.draft;
                        if (
                          currentDraft?.kind !== "seo" ||
                          queryClient.isMutating({
                            mutationKey: ["workspace-action", user!.id],
                          })
                        )
                          throw new Error("An SEO edit is required before saving.");
                        const base = currentDraft.base;
                        await save.mutateAsync({
                          base,
                          content: base.content,
                          seo,
                          owner: { id: currentDraft.id, revision: currentDraft.revision },
                        });
                      }}
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
                      onDownload={dirty || busy ? undefined : downloadHtml}
                    />
                  ),
                },
                {
                  key: "photos",
                  label: "Photos",
                  content: (
                    <PhotosPanel
                      key={`photos-${detail.id}-${editorEpoch}`}
                      article={detail}
                      saving={busy}
                      initialDraft={
                        draftSession?.kind === "photos" ? draftSession.editor : undefined
                      }
                      onDraftChange={updatePhotoDraft}
                      requestDiscard={requestAction}
                      onSave={async (photos) => {
                        const currentDraft =
                          queryClient.getQueryData<WorkspaceMemory>(memoryKey)?.draft;
                        if (
                          currentDraft?.kind !== "photos" ||
                          queryClient.isMutating({
                            mutationKey: ["workspace-action", user!.id],
                          })
                        )
                          throw new Error("A photo edit is required before saving.");
                        await photoSave.mutateAsync({
                          base: currentDraft.base,
                          photos,
                          owner: { id: currentDraft.id, revision: currentDraft.revision },
                        });
                      }}
                    />
                  ),
                },
                {
                  key: "sources",
                  label: "Sources",
                  content: (
                    <ResearchPanel
                      key={detail.id}
                      research={detail.content.research}
                      expanded
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
                      restoring={busy}
                      onRestore={(version) =>
                        requestAction(() =>
                          restore.mutate({ version, base: detail.current_version }),
                        )
                      }
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
