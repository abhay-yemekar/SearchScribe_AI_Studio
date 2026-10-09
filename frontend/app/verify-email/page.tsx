import type { Metadata } from "next";
import VerifyEmailForm from "@/features/auth/VerifyEmailForm";

export const metadata: Metadata = {
  title: "Verify email | SearchScribe",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default function VerifyEmailPage() {
  return <VerifyEmailForm />;
}
