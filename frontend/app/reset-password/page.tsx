import type { Metadata } from "next";
import ResetPasswordForm from "@/features/auth/ResetPasswordForm";

export const metadata: Metadata = {
  title: "Reset password | SearchScribe",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default function ResetPasswordPage() {
  return <ResetPasswordForm />;
}
