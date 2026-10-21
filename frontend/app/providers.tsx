"use client";

import { useEffect, useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { onIdentityChange } from "@/lib/auth/token-store";

export default function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            refetchOnWindowFocus: false,
            staleTime: 15_000,
          },
        },
      }),
  );

  // Cached articles and drafts belong to one person. An expired session leaves
  // them in memory so the same user gets their drafts back; anyone else signing
  // in on this tab must never see them.
  useEffect(() => onIdentityChange(() => queryClient.clear()), [queryClient]);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
