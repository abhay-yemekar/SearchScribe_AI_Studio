"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";

import { subscribe, getSnapshot, clearAccessToken } from "@/lib/auth/token-store";
import { fetchCurrentUser, logout as apiLogout } from "@/lib/api/auth";
import { refreshOnce } from "@/lib/api/client";
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
      if (!getSnapshot()) {
        // Silent refresh: exchanges the HttpOnly cookie for a fresh token.
        await refreshOnce();
      }
      if (getSnapshot()) {
        setUser(await fetchCurrentUser());
      }
    } catch {
      // Offline backend or expired session: stay logged out.
    } finally {
      setBootstrapping(false);
    }
  }, []);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  const logout = useCallback(async () => {
    await apiLogout();
    setUser(null);
    clearAccessToken();
    queryClient.clear();
    router.push("/");
  }, [queryClient, router]);

  return { token, user, bootstrapping, logout, setUser };
}
