"use client";

import type { User } from "@/lib/api/schemas";
import { getSnapshot, subscribe } from "./token-store";

type ProfileRequest = { token: string; expires: number; promise: Promise<User> };
let current: ProfileRequest | null = null;

// Private, per-tab memory only. A new identity or logout drops the old profile.
subscribe(() => {
  if (current?.token !== getSnapshot()) current = null;
});

export function primeSessionUser(user: User, token: string) {
  if (token !== getSnapshot()) return;
  current = { token, expires: Date.now() + 60_000, promise: Promise.resolve(user) };
}

export function loadSessionUser(
  loader: () => Promise<User>,
  force = false,
): Promise<User> {
  const token = getSnapshot();
  if (!force && token && current?.token === token && current.expires > Date.now()) {
    return current.promise;
  }
  const request: ProfileRequest = {
    token: token ?? "",
    expires: Infinity,
    promise: loader()
      .then((user) => {
        request.expires = Date.now() + 60_000;
        return user;
      })
      .catch((error) => {
        if (current === request) current = null;
        throw error;
      }),
  };
  if (token) current = request;
  return request.promise;
}
