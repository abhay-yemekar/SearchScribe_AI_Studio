"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { z } from "zod";
import { useSession } from "@/features/auth/useSession";
import GoogleSignIn from "@/features/auth/GoogleSignIn";
import { apiFetch } from "@/lib/api/client";
import { linkGoogle } from "@/lib/api/auth";
import BrandLogo from "@/components/brand/BrandLogo";

const connectionsSchema = z.object({ password: z.boolean(), google: z.boolean() });

export default function AccountPage() {
  const { token, bootstrapping } = useSession();
  const router = useRouter();
  const [connections, setConnections] = useState<z.infer<
    typeof connectionsSchema
  > | null>(null);
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => {
    if (!bootstrapping && !token) router.replace("/login");
    if (token)
      void apiFetch<unknown>("/api/v1/auth/connections")
        .then((data) => setConnections(connectionsSchema.parse(data)))
        .catch(() => setMessage("Could not load account connections."));
  }, [token, bootstrapping, router]);
  if (bootstrapping || !token)
    return (
      <p role="status" className="studio-shell min-h-screen p-8">
        Restoring session…
      </p>
    );
  return (
    <main className="studio-shell min-h-screen bg-[#f4f5f1] px-6 py-8 text-[#17252b] sm:py-12">
      <div className="mx-auto max-w-xl">
        <header className="flex flex-wrap items-center justify-between gap-5 border-b border-stone-300 pb-6">
          <Link href="/" aria-label="SearchScribe home">
            <BrandLogo />
          </Link>
          <nav aria-label="Account navigation" className="flex gap-5 text-sm font-medium">
            <Link href="/" className="hover:underline">
              Website
            </Link>
            <Link href="/dashboard" className="hover:underline">
              Back to workspace
            </Link>
          </nav>
        </header>
        <p className="mt-10 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
          Account / sign-in methods
        </p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight">Your account</h1>
        <h2 className="mt-6 text-xl">Google sign-in</h2>
        {connections?.google ? (
          <p className="mt-3">Google is linked to your account.</p>
        ) : connections?.password ? (
          <>
            <p className="my-4 text-slate-600">
              Confirm your password, then select the Google account with the same email.
              Your articles stay in this account.
            </p>
            <label htmlFor="link-password">Current password</label>
            <input
              id="link-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="mt-2 w-full rounded-lg border border-stone-300 bg-white p-3 focus-visible:outline-[#17252b]"
            />
            {password && (
              <GoogleSignIn
                onError={setMessage}
                onCredential={async (credential) => {
                  await linkGoogle(credential, password);
                  setPassword("");
                  setConnections({ password: true, google: true });
                  setMessage("Google linked. You can now use either sign-in method.");
                }}
              />
            )}
          </>
        ) : null}
        {message && (
          <p role="status" className="mt-4">
            {message}
          </p>
        )}
      </div>
    </main>
  );
}
