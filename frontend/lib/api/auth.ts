"use client";

import { apiFetch } from "./client";
import { tokenSchema, userSchema, type TokenPayload, type User } from "./schemas";
import { setAccessToken, clearAccessToken } from "@/lib/auth/token-store";
import { z } from "zod";

const authMessageSchema = z.object({ message: z.string() });

export async function forgotPassword(email: string) {
  return authMessageSchema.parse(
    await apiFetch<unknown>(
      "/api/v1/auth/password/forgot",
      {
        method: "POST",
        body: JSON.stringify({ email }),
        referrerPolicy: "no-referrer",
        cache: "no-store",
      },
      { skipAuth: true },
    ),
  );
}

export async function resetPassword(token: string, password: string) {
  const result = authMessageSchema.parse(
    await apiFetch<unknown>(
      "/api/v1/auth/password/reset",
      {
        method: "POST",
        body: JSON.stringify({ token, password }),
        referrerPolicy: "no-referrer",
        cache: "no-store",
      },
      { skipAuth: true },
    ),
  );
  clearAccessToken();
  return result;
}

export async function requestEmailVerification() {
  return authMessageSchema.parse(
    await apiFetch<unknown>("/api/v1/auth/email/verification/request", {
      method: "POST",
      referrerPolicy: "no-referrer",
      cache: "no-store",
    }),
  );
}

export async function verifyEmail(token: string) {
  return authMessageSchema.parse(
    await apiFetch<unknown>(
      "/api/v1/auth/email/verify",
      {
        method: "POST",
        body: JSON.stringify({ token }),
        referrerPolicy: "no-referrer",
        cache: "no-store",
      },
      { skipAuth: true },
    ),
  );
}

export async function signup(input: {
  name: string;
  email: string;
  password: string;
}): Promise<TokenPayload> {
  const payload = await apiFetch<TokenPayload>("/api/v1/auth/signup", {
    method: "POST",
    body: JSON.stringify(input),
  });
  const parsed = tokenSchema.parse(payload);
  setAccessToken(parsed.access_token, parsed.expires_in);
  return parsed;
}

export async function login(input: {
  email: string;
  password: string;
}): Promise<TokenPayload> {
  const payload = await apiFetch<TokenPayload>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(input),
  });
  const parsed = tokenSchema.parse(payload);
  setAccessToken(parsed.access_token, parsed.expires_in);
  return parsed;
}

export async function fetchCurrentUser(): Promise<User> {
  return userSchema.parse(await apiFetch<unknown>("/api/v1/auth/me"));
}

export async function googleLogin(credential: string): Promise<TokenPayload> {
  const payload = tokenSchema.parse(
    await apiFetch<unknown>(
      "/api/v1/auth/google",
      {
        method: "POST",
        body: JSON.stringify({ credential }),
      },
      { skipAuth: true },
    ),
  );
  setAccessToken(payload.access_token, payload.expires_in);
  return payload;
}

export async function linkGoogle(credential: string, password: string): Promise<void> {
  await apiFetch("/api/v1/auth/google/link", {
    method: "POST",
    body: JSON.stringify({ credential, password }),
  });
}

export async function logout(): Promise<void> {
  try {
    await apiFetch("/api/v1/auth/logout", { method: "POST" });
  } finally {
    clearAccessToken();
  }
}
