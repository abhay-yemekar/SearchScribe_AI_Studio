"use client";

import { ApiError, type ApiErrorShape } from "./errors";
import { clearAccessToken, getSnapshot, setAccessToken } from "@/lib/auth/token-store";

/**
 * Central typed API client.
 *
 * - Same-origin "/api/..." paths (Next.js rewrites proxy to the backend).
 * - Attaches the in-memory Bearer token automatically.
 * - On a 401 it silently rotates the refresh cookie once, then retries.
 * - Parses the backend error envelope into ApiError.
 */

export class UnauthorizedError extends Error {
  constructor() {
    super("Session expired");
    this.name = "UnauthorizedError";
  }
}

async function parseError(response: Response): Promise<ApiError> {
  let shape: ApiErrorShape | null = null;
  try {
    shape = (await response.json()) as ApiErrorShape;
  } catch {
    // Non-JSON error (proxy down, HTML error page, ...)
  }
  if (shape?.error?.code) {
    return new ApiError(response.status, shape);
  }
  return new ApiError(response.status, {
    error: {
      code: `HTTP_${response.status}`,
      message: `Request failed (${response.status}).`,
      request_id: "-",
    },
  });
}

async function rawRequest(
  path: string,
  init: RequestInit,
  token: string | null,
): Promise<Response> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(path, { ...init, headers, credentials: "include" });
}

async function tryRefresh(): Promise<boolean> {
  const response = await fetch("/api/v1/auth/refresh", {
    method: "POST",
    credentials: "include",
  });
  if (!response.ok) return false;
  const data = (await response.json()) as {
    access_token: string;
    expires_in: number;
  };
  setAccessToken(data.access_token, data.expires_in);
  return true;
}

let refreshPromise: Promise<boolean> | null = null;

/** Coalesces concurrent refresh attempts into one request. */
function refreshOnce(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = tryRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
  options: { skipAuth?: boolean; skipRefresh?: boolean } = {},
): Promise<T> {
  let response = await rawRequest(path, init, options.skipAuth ? null : getSnapshot());

  if (
    response.status === 401 &&
    !options.skipAuth &&
    !options.skipRefresh &&
    !path.startsWith("/api/v1/auth/")
  ) {
    const refreshed = await refreshOnce();
    if (refreshed) {
      response = await rawRequest(path, init, getSnapshot());
    } else {
      clearAccessToken();
      throw new UnauthorizedError();
    }
  }

  if (response.status === 204) {
    return undefined as T;
  }

  if (!response.ok) {
    throw await parseError(response);
  }

  return (await response.json()) as T;
}
