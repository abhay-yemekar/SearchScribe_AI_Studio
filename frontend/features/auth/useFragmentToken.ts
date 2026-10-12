"use client";

import { useLayoutEffect, useRef, useState } from "react";

export function isRecoveryToken(value: string | null): value is string {
  return value !== null && /^[A-Za-z0-9_-]{20,200}$/.test(value);
}

/** Keep link secrets only in this mounted component, never in browser storage. */
export function useFragmentToken(onLinkChange?: () => void) {
  const consumed = useRef(false);
  const mounted = useRef(false);
  const revision = useRef(0);
  const changeCallback = useRef(onLinkChange);
  const token = useRef<string | null>(null);
  const [snapshot, setSnapshot] = useState<{
    status: "loading" | "missing" | "ready" | "invalid";
    revision: number;
  }>({ status: "loading", revision: 0 });

  useLayoutEffect(() => {
    changeCallback.current = onLinkChange;
  });

  useLayoutEffect(() => {
    function readFragment() {
      const fragment = window.location.hash.slice(1);
      const values = new URLSearchParams(fragment);
      const candidates = values.getAll("token");
      const candidate = candidates.length === 1 ? candidates[0] : null;
      window.history.replaceState(window.history.state, "", window.location.pathname);
      token.current = isRecoveryToken(candidate) ? candidate : null;
      revision.current += 1;
      setSnapshot({
        status: token.current ? "ready" : fragment ? "invalid" : "missing",
        revision: revision.current,
      });
    }

    function hashChanged(event: HashChangeEvent) {
      // Ignore an older queued event after the user has moved to another URL.
      if (event.newURL && event.newURL !== window.location.href) return;
      readFragment();
      changeCallback.current?.();
    }

    mounted.current = true;
    // Retain the first read through StrictMode replay, but reinstall the listener.
    if (!consumed.current) {
      consumed.current = true;
      readFragment();
    }
    window.addEventListener("hashchange", hashChanged);
    return () => {
      mounted.current = false;
      window.removeEventListener("hashchange", hashChanged);
    };
  }, []);

  return {
    ...snapshot,
    getToken: () => token.current,
    isCurrent: (expectedRevision: number) =>
      mounted.current && revision.current === expectedRevision && !window.location.hash,
    discardToken: (
      expectedRevision: number,
      nextStatus: "missing" | "invalid" = "missing",
    ) => {
      if (
        !mounted.current ||
        revision.current !== expectedRevision ||
        window.location.hash
      )
        return;
      token.current = null;
      setSnapshot((current) => ({ ...current, status: nextStatus }));
    },
  };
}
