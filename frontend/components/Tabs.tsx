"use client";

import { useState, ReactNode } from "react";

type TabKey = "article" | "seo" | "html";

interface TabsProps {
  articleTab: ReactNode;
  seoTab: ReactNode;
  htmlTab: ReactNode;
}

export default function Tabs({ articleTab, seoTab, htmlTab }: TabsProps) {
  const [active, setActive] = useState<TabKey>("article");

  const baseButton =
    "px-4 py-2 text-sm font-medium border-b-2 transition-colors";
  const inactive =
    "border-transparent text-gray-400 hover:text-white hover:border-gray-500";
  const activeCls = "border-blue-500 text-white";

  return (
    <div className="h-full flex flex-col rounded-xl bg-slate-900/70 border border-slate-700">
      {/* Tabs Header */}
      <div className="flex border-b border-slate-700">
        <button
          className={`${baseButton} ${active === "article" ? activeCls : inactive}`}
          onClick={() => setActive("article")}
        >
          Article
        </button>

        <button
          className={`${baseButton} ${active === "seo" ? activeCls : inactive}`}
          onClick={() => setActive("seo")}
        >
          SEO Metadata
        </button>

        <button
          className={`${baseButton} ${active === "html" ? activeCls : inactive}`}
          onClick={() => setActive("html")}
        >
          HTML Preview
        </button>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto p-4">
        {active === "article" && articleTab}
        {active === "seo" && seoTab}
        {active === "html" && htmlTab}
      </div>
    </div>
  );
}
