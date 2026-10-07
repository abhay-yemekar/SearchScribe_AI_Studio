"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { z } from "zod";
import { useSession } from "@/features/auth/useSession";
import GoogleSignIn from "@/features/auth/GoogleSignIn";
import { apiFetch } from "@/lib/api/client";
import { linkGoogle } from "@/lib/api/auth";

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
      <p role="status" className="p-8">
        Restoring session…
      </p>
    );
  return (
    <main className="mx-auto max-w-xl px-6 py-12">
      <Link href="/dashboard" className="text-teal-800 underline">
        Back to workspace
      </Link>
      <h1 className="mt-8 font-serif text-3xl">Your account</h1>
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
            className="mt-2 w-full rounded border border-stone-300 p-3"
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
    </main>
  );
}
