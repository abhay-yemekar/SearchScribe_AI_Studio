"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import AuthForm from "@/features/auth/AuthForm";
import { useSession } from "@/features/auth/useSession";
import { Spinner } from "@/components/shared/States";

export default function HomePage() {
  const router = useRouter();
  const { token, bootstrapping } = useSession();

  useEffect(() => {
    if (!bootstrapping && token) router.replace("/dashboard");
  }, [bootstrapping, token, router]);

  if (bootstrapping) {
    return (
      <div className="flex min-h-screen items-center justify-center gap-3 text-slate-400">
        <Spinner className="h-6 w-6" /> Loading SearchScribe…
      </div>
    );
  }

  return <AuthForm />;
}
