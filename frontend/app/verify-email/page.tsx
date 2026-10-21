import type { Metadata } from "next";
import VerifyEmailForm from "@/features/auth/VerifyEmailForm";

// Nonce CSP from proxy.ts needs a per-request render (see lib/security-headers.mjs).
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Verify email | SearchScribe",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default function VerifyEmailPage() {
  return <VerifyEmailForm />;
}
