"use client";

import { useEffect, useEffectEvent, useRef, useState } from "react";

export const UNDO_DELETE_MS = 10_000;

export type PendingDelete = { id: number; title: string; wasOpen: boolean };

/**
 * Deleting hides an article at once and sends the real delete after
 * UNDO_DELETE_MS, so a stray click can be undone. One delete waits at a time:
 * a second delete, or leaving the workspace, sends the waiting one straight
 * away. Closing the page sends it with `keepalive` so the request survives.
 */
export function useUndoableDelete({
  commit,
  commitOnPageHide,
}: {
  commit: (id: number) => void;
  commitOnPageHide: (id: number) => void;
}) {
  const [pending, setPending] = useState<PendingDelete | null>(null);
  // Mirrors `pending` for the unmount cleanup; written only where state changes.
  const pendingRef = useRef<PendingDelete | null>(null);
  const send = useEffectEvent((id: number) => commit(id));
  const sendOnPageHide = useEffectEvent((id: number) => commitOnPageHide(id));

  const settle = () => {
    pendingRef.current = null;
    setPending(null);
  };

  useEffect(() => {
    if (!pending) return;
    const timer = window.setTimeout(() => {
      settle();
      send(pending.id);
    }, UNDO_DELETE_MS);
    const onPageHide = () => {
      settle();
      sendOnPageHide(pending.id);
    };
    window.addEventListener("pagehide", onPageHide);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("pagehide", onPageHide);
    };
  }, [pending]);

  useEffect(
    () => () => {
      if (pendingRef.current) send(pendingRef.current.id);
    },
    [],
  );

  return {
    pending,
    schedule: (next: PendingDelete) => {
      if (pendingRef.current) commit(pendingRef.current.id);
      pendingRef.current = next;
      setPending(next);
    },
    undo: (): PendingDelete | null => {
      const restored = pendingRef.current;
      settle();
      return restored;
    },
  };
}
