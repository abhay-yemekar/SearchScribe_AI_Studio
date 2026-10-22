"use client";

import { useEffect, useRef } from "react";

/** Mount with a `key` per item so focus moves to Undo for each new delete. */
export default function UndoToast({
  message,
  onUndo,
}: {
  message: string;
  onUndo: () => void;
}) {
  const undoRef = useRef<HTMLButtonElement>(null);
  // The deleted row's button just disappeared; keep keyboard focus nearby.
  useEffect(() => {
    undoRef.current?.focus();
  }, []);

  return (
    <div
      role="status"
      className="fixed bottom-4 left-1/2 z-50 flex w-[calc(100%-2rem)] max-w-md -translate-x-1/2 items-center justify-between gap-3 rounded-lg bg-[#17252b] px-4 py-3 text-sm text-white shadow-lg"
    >
      <span className="min-w-0 truncate">{message}</span>
      <button
        ref={undoRef}
        type="button"
        onClick={onUndo}
        className="shrink-0 rounded-md border border-white/40 px-3 py-1 font-semibold hover:bg-white/10 focus-visible:outline-solid focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
      >
        Undo
      </button>
    </div>
  );
}
