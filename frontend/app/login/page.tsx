import type { Metadata } from "next";
import LoginClient from "./LoginClient";

// Nonce CSP from proxy.ts needs a per-request render (see lib/security-headers.mjs).
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Log in or sign up | SearchScribe",
  robots: { index: false, follow: false },
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ mode?: string }>;
}) {
  const { mode } = await searchParams;
  return <LoginClient initialMode={mode === "signup" ? "signup" : "login"} />;
}
