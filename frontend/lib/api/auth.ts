"use client";

import { apiFetch } from "./client";
import { tokenSchema, userSchema, type TokenPayload, type User } from "./schemas";
import { setAccessToken, clearAccessToken } from "@/lib/auth/token-store";

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

export async function logout(): Promise<void> {
  try {
    await apiFetch("/api/v1/auth/logout", { method: "POST" });
  } finally {
    clearAccessToken();
  }
}
