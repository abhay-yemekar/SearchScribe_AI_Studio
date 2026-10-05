"use client";

import { useId, useRef, type ReactNode } from "react";

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
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
      <div
        role="tablist"
        aria-label="Article views"
        className="flex shrink-0 gap-1 overflow-x-auto border-b border-stone-200 bg-stone-50 px-2"
        onKeyDown={(event) => {
          const index = tabs.findIndex((t) => t.key === active);
          const next =
            event.key === "ArrowRight"
              ? (index + 1) % tabs.length
              : event.key === "ArrowLeft"
                ? (index - 1 + tabs.length) % tabs.length
                : event.key === "Home"
                  ? 0
                  : event.key === "End"
                    ? tabs.length - 1
                    : -1;
          if (next < 0) return;
          event.preventDefault();
          onChange(tabs[next].key);
          buttons.current[next]?.focus();
        }}
      >
        {tabs.map((tab, index) => {
          const isActive = tab.key === active;
          return (
            <button
              key={tab.key}
              ref={(node) => {
                buttons.current[index] = node;
              }}
              role="tab"
              id={`${baseId}-tab-${tab.key}`}
              aria-selected={isActive}
              aria-controls={`${baseId}-panel-${tab.key}`}
              tabIndex={isActive ? 0 : -1}
              onClick={() => onChange(tab.key)}
              className={`shrink-0 whitespace-nowrap border-b-2 px-4 py-3 text-sm font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-teal-600 ${
                isActive
                  ? "border-teal-700 text-teal-800"
                  : "border-transparent text-slate-500 hover:text-slate-900"
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
        className="min-h-0 flex-1 overflow-auto p-4 sm:p-6 lg:p-8"
      >
        {tabs.find((t) => t.key === active)?.content}
      </div>
    </div>
  );
}
