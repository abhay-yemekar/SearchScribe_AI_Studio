"use client";

import { useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import Tabs from "@/components/Tabs";
import HtmlPreview from "@/components/HtmlPreview";
import ArticlePreview from "@/components/ArticlePreview";   // <-- added import

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type HistoryItem = {
  id: number;
  query: string;
  article: string;
  seo_metadata: {
    title?: string;
    description?: string;
  } | null;
  html: string;
  created_at: string;
};

export default function DashboardPage() {
  const router = useRouter();

  const [query, setQuery] = useState("");
  const [articleText, setArticleText] = useState("");
  const [seoTitle, setSeoTitle] = useState("");
  const [seoDescription, setSeoDescription] = useState("");
  const [htmlPreview, setHtmlPreview] = useState("");

  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [userName, setUserName] = useState<string | null>(null);

  const getToken = () =>
    typeof window !== "undefined"
      ? localStorage.getItem("token")
      : null;

  const fetchHistory = async () => {
    try {
      setLoadingHistory(true);
      const token = getToken();
      if (!token) return;

      const res = await fetch(
        `${API_BASE}/content/history?limit=20`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!res.ok) return;

      const data: HistoryItem[] = await res.json();
      setHistory(data);
    } catch (err) {
      console.error("Failed to load history", err);
    } finally {
      setLoadingHistory(false);
    }
  };

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push("/");
      return;
    }

    if (typeof window !== "undefined") {
      const storedName = localStorage.getItem("user_name");
      if (storedName) setUserName(storedName);
    }

    fetchHistory();
  }, []); 

  const handleGenerate = async () => {
    try {
      setError(null);

      if (!query.trim()) {
        setError("Please enter a topic.");
        return;
      }

      const token = getToken();
      if (!token) return router.push("/");

      setGenerating(true);

      const res = await fetch(`${API_BASE}/content/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ query }),
      });

      if (!res.ok) throw new Error("Generation failed");

      const data = await res.json();
      const seo = data.seo_metadata || {};

      setArticleText(data.article || "");
      setSeoTitle(seo.title || "");
      setSeoDescription(seo.description || "");
      setHtmlPreview(data.html || "");

      fetchHistory();
    } catch (err: any) {
      setError(err?.message || "Error generating content.");
    } finally {
      setGenerating(false);
    }
  };

  const handleRegenerateGenZ = async () => {
    try {
      setError(null);

      if (!articleText.trim()) {
        setError("Please generate content first.");
        return;
      }

      const token = getToken();
      if (!token) return router.push("/");

      setRegenerating(true);

      const res = await fetch(`${API_BASE}/content/regenerate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          article: articleText,
          style_instruction:
            "Rewrite this article in a casual, fun, Gen Z tone while keeping SEO intact.",
        }),
      });

      if (!res.ok) throw new Error("Regenerate failed");

      const data = await res.json();

      setArticleText(data.article || articleText);
      setHtmlPreview(data.html || htmlPreview);

      fetchHistory();
    } catch (err) {
      setError("Failed to regenerate article.");
    } finally {
      setRegenerating(false);
    }
  };

  const handleLoadFromHistory = (item: HistoryItem) => {
    setQuery(item.query);
    setArticleText(item.article);
    setSeoTitle(item.seo_metadata?.title || "");
    setSeoDescription(item.seo_metadata?.description || "");
    setHtmlPreview(item.html);
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    router.push("/");
  };

  const handleDownloadHtml = () => {
    if (!htmlPreview) return;

    const blob = new Blob([htmlPreview], {
      type: "text/html;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = "generated.html";
    a.click();

    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex h-screen bg-slate-950 text-white">
      {/* Sidebar */}
      <aside className="w-72 border-r border-slate-800 p-4 bg-slate-900/60 flex flex-col">
        <div>
          <h2 className="text-base font-semibold mb-4">
            SearchScribe AI Studio
          </h2>

          <button
            className="w-full py-2 mb-2 bg-blue-600 hover:bg-blue-700 rounded"
            onClick={handleGenerate}
            disabled={generating}
          >
            {generating ? "Generating…" : "Generate Content"}
          </button>

          <button
            className="w-full py-2 mb-2 bg-rose-500 hover:bg-rose-600 rounded"
            onClick={handleRegenerateGenZ}
            disabled={regenerating}
          >
            {regenerating ? "Regenerating…" : "Regenerate for GenZ"}
          </button>
        </div>

        {/* History */}
        <div className="mt-6 flex-1 flex flex-col">
          <h3 className="text-sm font-semibold text-slate-300 mb-2">
            History
          </h3>

          {loadingHistory ? (
            <p className="text-xs text-slate-500">
              Loading history…
            </p>
          ) : history.length === 0 ? (
            <p className="text-xs text-slate-500">
              No history found.
            </p>
          ) : (
            <div className="space-y-1 overflow-y-auto text-sm max-h-80 pr-1">
              {history.map((item) => (
                <button
                  key={item.id}
                  onClick={() => handleLoadFromHistory(item)}
                  className="w-full text-left px-2 py-1 rounded-md hover:bg-slate-800"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-slate-400">
                      ARTICLE + SEO
                    </span>
                    <span className="text-[10px] text-slate-500">
                      {new Date(
                        item.created_at
                      ).toLocaleTimeString()}
                    </span>
                  </div>
                  <div className="text-xs text-slate-200 truncate">
                    {item.query}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </aside>

      {/* Main Area */}
      <main className="flex-1 p-6 flex flex-col gap-4">
        {/* Top bar */}
        <div className="flex items-center justify-between mb-2">
          <h1 className="text-2xl font-bold tracking-tight">
            SearchScribe AI Studio
          </h1>

          <div className="flex items-center gap-3">
            {userName && (
              <span className="text-sm text-slate-300">
                Hi, {userName}
              </span>
            )}
            <button
              onClick={handleLogout}
              className="px-3 py-1.5 text-sm rounded border border-slate-600 hover:bg-slate-800"
            >
              Logout
            </button>
          </div>
        </div>

        {/* Query */}
        <div>
          <label className="block text-sm mb-1 text-slate-300">
            Topic / Search query
          </label>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g., Things to do in Pune"
            className="w-full p-2 bg-slate-900 border border-slate-700 rounded text-sm"
          />
          {error && (
            <p className="text-xs text-red-400 mt-1">{error}</p>
          )}
        </div>

        {/* Tabs */}
        <div className="flex-1">
          <Tabs
            articleTab={
              <ArticlePreview content={articleText} />   // <-- only change
            }
            seoTab={
              <div className="space-y-4">
                <div>
                  <label className="block text-sm mb-1">
                    SEO Title
                  </label>
                  <input
                    value={seoTitle}
                    onChange={(e) =>
                      setSeoTitle(e.target.value)
                    }
                    className="w-full p-2 bg-slate-800 border border-slate-700 rounded text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm mb-1">
                    SEO Description
                  </label>
                  <textarea
                    value={seoDescription}
                    onChange={(e) =>
                      setSeoDescription(e.target.value)
                    }
                    className="w-full p-2 bg-slate-800 border border-slate-700 rounded h-32 text-sm resize-none"
                  />
                </div>
              </div>
            }
            htmlTab={
              <HtmlPreview
                html={htmlPreview}
                onDownload={handleDownloadHtml}
              />
            }
          />
        </div>
      </main>
    </div>
  );
}
