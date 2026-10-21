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
// The last signed-in user, kept after the token is cleared so the next sign-in
// in this tab can tell whether the person changed.
let subject: string | null = null;
const listeners = new Set<() => void>();
const identityListeners = new Set<() => void>();

function emit() {
  listeners.forEach((listener) => listener());
}

/** The JWT `sub` claim. The API verifies tokens; this only compares identities. */
function tokenSubject(token: string): string | null {
  try {
    const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const sub: unknown = JSON.parse(atob(payload)).sub;
    return typeof sub === "string" || typeof sub === "number" ? String(sub) : null;
  } catch {
    return null;
  }
}

/**
 * Runs when a token for a different user replaces the previous one in this tab,
 * before components see the new token. Callers drop private cached data here.
 */
export function onIdentityChange(listener: () => void): () => void {
  identityListeners.add(listener);
  return () => identityListeners.delete(listener);
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getSnapshot(): string | null {
  return accessToken;
}

export function setAccessToken(token: string, expiresInSeconds?: number) {
  const next = tokenSubject(token);
  const changed = subject !== null && next !== subject;
  subject = next;
  if (changed) identityListeners.forEach((listener) => listener());
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
