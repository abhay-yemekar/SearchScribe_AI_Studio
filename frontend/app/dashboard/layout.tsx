import type { Metadata } from "next";

export const metadata: Metadata = { robots: { index: false, follow: false } };
// Nonce CSP from proxy.ts needs a per-request render (see lib/security-headers.mjs).
export const dynamic = "force-dynamic";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return children;
}
