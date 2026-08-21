"use client";

/**
 * In-memory access token store.
 *
 * The access token never touches localStorage (XSS exposure) — it lives in a
 * module-level variable for the lifetime of the tab. On reload, the app
 * silently exchanges the HttpOnly refresh cookie for a new access token.
 */

let accessToken: string | null = null;
let expiresAt: number | null = null;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((listener) => listener());
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getSnapshot(): string | null {
  return accessToken;
}

export function setAccessToken(token: string, expiresInSeconds?: number) {
  accessToken = token;
  expiresAt = expiresInSeconds ? Date.now() + expiresInSeconds * 1000 : null;
  emit();
}

export function clearAccessToken() {
  accessToken = null;
  expiresAt = null;
  emit();
}

export function isTokenExpiringSoon(): boolean {
  if (!accessToken || expiresAt === null) return true;
  return Date.now() > expiresAt - 30_000;
}
