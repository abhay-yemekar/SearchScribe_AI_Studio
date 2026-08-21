"use client";

import { useId, type ReactNode } from "react";

export type TabDefinition = { key: string; label: string; content: ReactNode };

/** Accessible tab strip (role=tablist, aria-selected, keyboard arrows). */
export default function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: TabDefinition[];
  active: string;
  onChange: (key: string) => void;
}) {
  const baseId = useId();

  return (
    <div className="flex h-full min-h-0 flex-col rounded-xl border border-slate-700 bg-slate-900/70">
      <div
        role="tablist"
        aria-label="Article views"
        className="flex gap-1 border-b border-slate-700 px-2"
        onKeyDown={(event) => {
          const index = tabs.findIndex((t) => t.key === active);
          if (event.key === "ArrowRight" && index < tabs.length - 1) {
            onChange(tabs[index + 1].key);
          } else if (event.key === "ArrowLeft" && index > 0) {
            onChange(tabs[index - 1].key);
          }
        }}
      >
        {tabs.map((tab) => {
          const isActive = tab.key === active;
          return (
            <button
              key={tab.key}
              role="tab"
              id={`${baseId}-tab-${tab.key}`}
              aria-selected={isActive}
              aria-controls={`${baseId}-panel-${tab.key}`}
              tabIndex={isActive ? 0 : -1}
              onClick={() => onChange(tab.key)}
              className={`border-b-2 px-4 py-2.5 text-sm font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-blue-500 ${
                isActive
                  ? "border-blue-500 text-white"
                  : "border-transparent text-slate-400 hover:text-white"
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
      <div
        role="tabpanel"
        id={`${baseId}-panel-${active}`}
        aria-labelledby={`${baseId}-tab-${active}`}
        className="min-h-0 flex-1 overflow-auto p-4"
      >
        {tabs.find((t) => t.key === active)?.content}
      </div>
    </div>
  );
}
