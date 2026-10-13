"use client";

import { useState } from "react";

export type EditorDraft<T> = { original: T; value: T; editing: boolean };

export function draftIsDirty<T>(draft: EditorDraft<T> | null | undefined): boolean {
  return (
    !!draft?.editing && JSON.stringify(draft.value) !== JSON.stringify(draft.original)
  );
}

export function useEditorDraft<T>({
  source,
  saving,
  initialDraft,
  onDraftChange,
  requestDiscard,
  onSave,
}: {
  source: T;
  saving: boolean;
  initialDraft?: EditorDraft<T>;
  onDraftChange?: (draft: EditorDraft<T>) => void;
  requestDiscard?: (action: () => void) => void;
  onSave: (value: T) => void | Promise<void>;
}) {
  const [snapshot, setSnapshot] = useState<EditorDraft<T>>(
    () =>
      initialDraft ?? {
        original: structuredClone(source),
        value: structuredClone(source),
        editing: false,
      },
  );
  const [confirmCancel, setConfirmCancel] = useState(false);
  const dirty = draftIsDirty(snapshot);
  const commit = (next: EditorDraft<T>) => {
    setSnapshot(next);
    onDraftChange?.(next);
  };
  const discard = () => {
    if (saving) return;
    commit({
      original: structuredClone(source),
      value: structuredClone(source),
      editing: false,
    });
    setConfirmCancel(false);
  };

  return {
    draft: snapshot.value,
    editing: snapshot.editing,
    dirty,
    confirmCancel,
    keep: () => setConfirmCancel(false),
    discard,
    start: () => {
      if (!saving)
        commit({
          original: structuredClone(source),
          value: structuredClone(source),
          editing: true,
        });
    },
    change: (value: T | ((current: T) => T)) => {
      if (!saving)
        commit({
          ...snapshot,
          value:
            typeof value === "function"
              ? (value as (current: T) => T)(snapshot.value)
              : value,
        });
    },
    cancel: () => {
      if (saving) return;
      if (!dirty) discard();
      else if (requestDiscard) requestDiscard(discard);
      else setConfirmCancel(true);
    },
    submit: async (value: T = snapshot.value) => {
      if (saving || !dirty) return;
      try {
        await onSave(value);
        // Controlled callers own successful cleanup, including across route remounts.
        if (!onDraftChange)
          commit({
            original: structuredClone(value),
            value: structuredClone(value),
            editing: false,
          });
      } catch {
        // The caller renders the save error. Keep the submitted draft intact for retry.
      }
    },
  };
}
