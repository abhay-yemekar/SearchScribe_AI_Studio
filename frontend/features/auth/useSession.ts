"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";

import { subscribe, getSnapshot, clearAccessToken } from "@/lib/auth/token-store";
import { fetchCurrentUser, logout as apiLogout } from "@/lib/api/auth";
import type { User } from "@/lib/api/schemas";

/**
 * Session hook.
 * - `token` mirrors the in-memory access token via useSyncExternalStore.
 * - `bootstrap()` performs the silent refresh-cookie exchange on first load.
 */
export function useSession() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const token = useSyncExternalStore(subscribe, getSnapshot, () => null);
  const [user, setUser] = useState<User | null>(null);
  const [bootstrapping, setBootstrapping] = useState(true);

  const bootstrap = useCallback(async () => {
    setBootstrapping(true);
    try {
      if (!token) {
        // Silent refresh: exchanges the HttpOnly cookie for a fresh token.
        const response = await fetch("/api/v1/auth/refresh", {
          method: "POST",
          credentials: "include",
        });
        if (response.ok) {
          const data = (await response.json()) as {
            access_token: string;
            expires_in: number;
          };
          const { setAccessToken } = await import("@/lib/auth/token-store");
          setAccessToken(data.access_token, data.expires_in);
        }
      }
      if (getSnapshot()) {
        setUser(await fetchCurrentUser());
      }
    } catch {
      // Offline backend or expired session: stay logged out.
    } finally {
      setBootstrapping(false);
    }
  }, [token]);

  useEffect(() => {
    void bootstrap();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const logout = useCallback(async () => {
    await apiLogout();
    setUser(null);
    clearAccessToken();
    queryClient.clear();
    router.push("/");
  }, [queryClient, router]);

  return { token, user, bootstrapping, logout, setUser };
}
