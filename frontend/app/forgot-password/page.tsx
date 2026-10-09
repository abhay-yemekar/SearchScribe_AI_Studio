import type { Metadata } from "next";
import ForgotPasswordForm from "@/features/auth/ForgotPasswordForm";

export const metadata: Metadata = {
  title: "Forgot password | SearchScribe",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default function ForgotPasswordPage() {
  return <ForgotPasswordForm />;
}
