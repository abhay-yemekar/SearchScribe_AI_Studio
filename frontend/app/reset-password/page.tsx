import type { Metadata } from "next";
import ResetPasswordForm from "@/features/auth/ResetPasswordForm";

// Nonce CSP from proxy.ts needs a per-request render (see lib/security-headers.mjs).
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Reset password | SearchScribe",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default function ResetPasswordPage() {
  return <ResetPasswordForm />;
}
