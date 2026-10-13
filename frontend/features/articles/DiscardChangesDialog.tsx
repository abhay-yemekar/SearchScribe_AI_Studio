"use client";

import { useEffect, useId, useRef } from "react";

export default function DiscardChangesDialog({
  onKeep,
  onDiscard,
}: {
  onKeep: () => void;
  onDiscard: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const keep = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    const node = dialog.current;
    node?.showModal();
    keep.current?.focus();
    return () => {
      node?.close();
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, []);

  return (
    <dialog
      ref={dialog}
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      onCancel={(event) => {
        event.preventDefault();
        onKeep();
      }}
      className="w-[calc(100%_-_2rem)] max-w-md rounded-xl border border-stone-300 bg-white p-6 text-slate-900 shadow-xl backdrop:bg-black/50"
    >
      <h2 id={titleId} className="text-lg font-semibold">
        Discard unsaved changes?
      </h2>
      <p id={descriptionId} className="mt-2 text-sm leading-relaxed text-slate-600">
        Your latest edits have not been saved. Keep editing, or discard them to continue.
      </p>
      <div className="mt-6 flex flex-wrap justify-end gap-3">
        <button
          ref={keep}
          type="button"
          onClick={onKeep}
          className="rounded-lg border border-stone-300 px-4 py-2 text-sm font-semibold"
        >
          Keep editing
        </button>
        <button
          type="button"
          onClick={onDiscard}
          className="rounded-lg bg-rose-700 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-800"
        >
          Discard changes
        </button>
      </div>
    </dialog>
  );
}
