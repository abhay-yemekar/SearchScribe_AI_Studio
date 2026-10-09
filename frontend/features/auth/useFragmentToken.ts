"use client";

import { useLayoutEffect, useRef, useState } from "react";

/** Keep link secrets only in this mounted component, never in browser storage. */
export function useFragmentToken() {
  const consumed = useRef(false);
  const token = useRef<string | null>(null);
  const [status, setStatus] = useState<"loading" | "missing" | "ready">("loading");

  useLayoutEffect(() => {
    // The guard retains the first read through StrictMode's effect replay.
    if (consumed.current) return;
    consumed.current = true;
    const values = new URLSearchParams(window.location.hash.slice(1));
    const candidate = values.get("token");
    window.history.replaceState(window.history.state, "", window.location.pathname);
    token.current = candidate && candidate.length <= 512 ? candidate : null;
    // Reading and clearing the browser URL is this effect's external boundary.
    setStatus(token.current ? "ready" : "missing");
  }, []);

  return {
    status,
    getToken: () => token.current,
    discardToken: () => {
      token.current = null;
      setStatus("missing");
    },
  };
}
