import type { Metadata } from "next";
import ForgotPasswordForm from "@/features/auth/ForgotPasswordForm";

// Nonce CSP from proxy.ts needs a per-request render (see lib/security-headers.mjs).
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Forgot password | SearchScribe",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default function ForgotPasswordPage() {
  return <ForgotPasswordForm />;
}
