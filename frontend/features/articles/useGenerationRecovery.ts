"use client";

import { useRef, useState } from "react";
import { z } from "zod";
import { apiFetch } from "@/lib/api/client";
import { isApiError } from "@/lib/api/errors";

const operationSchema = z.object({
  status: z.enum(["processing", "completed", "failed", "interrupted"]),
  article_id: z.number().int().positive().nullable(),
});

/** Only a request identifier is persisted, never credentials or article text. */
export function useGenerationRecovery(userId: number) {
  const storageKey = `searchscribe:generation-request:${userId}`;
  const [pendingKey, setPendingKey] = useState<string | null>(() => {
    try {
      const stored = sessionStorage.getItem(storageKey);
      return stored && /^[A-Za-z0-9_-]{16,64}$/.test(stored) ? stored : null;
    } catch {
      return null;
    }
  });
  const activeKey = useRef(pendingKey);
  const [checking, setChecking] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  function remember(key: string | null) {
    activeKey.current = key;
    setPendingKey(key);
    try {
      if (key) sessionStorage.setItem(storageKey, key);
      else sessionStorage.removeItem(storageKey);
    } catch {
      // A blocked store still permits in-memory recovery for this mounted page.
    }
  }

  async function run<T>(action: (key: string) => Promise<T>): Promise<T> {
    if (activeKey.current) {
      throw new Error("Check the previous generation request before starting another.");
    }
    const key = crypto.randomUUID();
    remember(key);
    setNotice(null);
    try {
      const result = await action(key);
      remember(null);
      return result;
    } catch (error) {
      // Definitive rejection before work (or a handled provider failure) is safe
      // to dismiss. Network/proxy/unknown errors need the journal lookup first.
      if (isApiError(error) && [
        "GENERATION_DAILY_LIMIT", "TOPIC_CLARIFICATION_REQUIRED", "RATE_LIMITED",
        "AI_DAILY_LIMIT_REACHED", "AI_SERVICE_BUSY", "VALIDATION_ERROR",
        "UNKNOWN_STYLE", "REWRITE_INPUT_TOO_LONG", "QUERY_TOO_LONG",
        "GENERATION_FAILED", "REWRITE_FAILED", "AI_PROVIDER_UNAVAILABLE",
        "CURRENT_SOURCES_NOT_FOUND", "CURRENT_SOURCES_UNAVAILABLE", "RESEARCH_NOT_CONFIGURED",
        "RESEARCH_PLANNING_UNAVAILABLE", "EVIDENCE_REVIEW_UNAVAILABLE",
        "STALE_ARTICLE_VERSION", "REWRITE_PHOTO_LAYOUT_CHANGED",
      ].includes(error.code)) remember(null);
      throw error;
    }
  }

  async function check(): Promise<number | null> {
    const key = activeKey.current;
    if (!key || checking) return null;
    setChecking(true);
    setNotice(null);
    try {
      const status = operationSchema.parse(await apiFetch<unknown>(
        `/api/v1/generation-requests/${key}`,
      ));
      if (status.status === "processing") {
        setNotice("Your request is still running. Check again shortly; no extra AI call was made.");
        return null;
      }
      remember(null);
      if (status.status === "completed" && status.article_id) return status.article_id;
      setNotice(status.status === "completed"
        ? "The original article was deleted. No new draft was generated."
        : "The request did not complete. Your saved articles are available; you can try again.");
      return null;
    } catch (error) {
      if (isApiError(error) && error.status === 404) {
        remember(null);
        setNotice("No accepted request was found. You can try generating again.");
      } else {
        setNotice("Unable to check right now. Your request is kept; try checking again shortly.");
      }
      return null;
    } finally {
      setChecking(false);
    }
  }

  return { pendingKey, checking, notice, run, check };
}
