"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";

import { subscribe, getSnapshot, clearAccessToken } from "@/lib/auth/token-store";
import { fetchCurrentUser, logout as apiLogout } from "@/lib/api/auth";
import { refreshOnce } from "@/lib/api/client";
import type { User } from "@/lib/api/schemas";

// Public navigation can remount this hook on every page. Remember only a recent
// missing session, in this tab; protected routes always check the cookie again.
const PUBLIC_NO_SESSION_TTL_MS = 30_000;
let publicNoSessionUntil = 0;

/**
 * Session hook.
 * - `token` mirrors the in-memory access token via useSyncExternalStore.
 * - `bootstrap()` performs the silent refresh-cookie exchange on first load.
 */
export function useSession({ publicView = false }: { publicView?: boolean } = {}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const token = useSyncExternalStore(subscribe, getSnapshot, () => null);
  const [user, setUser] = useState<User | null>(null);
  const [bootstrapping, setBootstrapping] = useState(true);

  const bootstrap = useCallback(async () => {
    setBootstrapping(true);
    try {
      if (!getSnapshot()) {
        if (publicView && Date.now() < publicNoSessionUntil) return;
        // Silent refresh: exchanges the HttpOnly cookie for a fresh token.
        await refreshOnce(
          publicView
            ? {
                onUnauthorized: () => {
                  publicNoSessionUntil = Date.now() + PUBLIC_NO_SESSION_TTL_MS;
                },
              }
            : undefined,
        );
      }
      if (getSnapshot()) {
        publicNoSessionUntil = 0;
        setUser(await fetchCurrentUser());
      }
    } catch {
      // Offline backend or expired session: stay logged out.
    } finally {
      setBootstrapping(false);
    }
  }, [publicView]);

  useEffect(() => {
    // Session bootstrap is the effect's external synchronization boundary.
    // eslint-disable-next-line react-hooks/set-state-in-effect
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
