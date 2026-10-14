"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { z } from "zod";
import { useSession } from "@/features/auth/useSession";
import GoogleSignIn from "@/features/auth/GoogleSignIn";
import PasswordManagement from "@/features/auth/PasswordManagement";
import { apiFetch } from "@/lib/api/client";
import { fetchCurrentUser, linkGoogle, requestEmailVerification } from "@/lib/api/auth";
import BrandLogo from "@/components/brand/BrandLogo";
import { recoveryError } from "@/features/auth/recovery-errors";
import { recoveryButtonClass, recoveryLinkClass } from "@/features/auth/RecoveryShell";
import { Spinner } from "@/components/shared/States";

const connectionsSchema = z.object({ password: z.boolean(), google: z.boolean() });

export default function AccountPage() {
  const { token, user, setUser, bootstrapping } = useSession();
  const router = useRouter();
  const [connections, setConnections] = useState<z.infer<
    typeof connectionsSchema
  > | null>(null);
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [verificationMessage, setVerificationMessage] = useState<string | null>(null);
  const [verificationError, setVerificationError] = useState<string | null>(null);
  const [verificationBusy, setVerificationBusy] = useState(false);
  const [statusBusy, setStatusBusy] = useState(false);
  const [connectionsBusy, setConnectionsBusy] = useState(true);
  const [connectionsError, setConnectionsError] = useState<string | null>(null);
  const [connectionsAttempt, setConnectionsAttempt] = useState(0);
  const [completion, setCompletion] = useState<string | null>(null);
  const completed = useRef(false);
  useEffect(() => {
    let cancelled = false;
    if (!bootstrapping && !token && !completed.current) router.replace("/login");
    if (token && !completed.current)
      void apiFetch<unknown>("/api/v1/auth/connections")
        .then((data) => {
          if (!cancelled && !completed.current) {
            setConnections(connectionsSchema.parse(data));
            setConnectionsError(null);
          }
        })
        .catch(() => {
          if (!cancelled && !completed.current)
            setConnectionsError("Could not load account connections. Try again.");
        })
        .finally(() => {
          if (!cancelled && !completed.current) setConnectionsBusy(false);
        });
    return () => {
      cancelled = true;
    };
  }, [token, bootstrapping, router, connectionsAttempt]);

  function passwordComplete(successMessage: string) {
    completed.current = true;
    setCompletion(successMessage);
    setPassword("");
    setMessage("");
    setUser(null);
  }

  async function sendVerification() {
    setVerificationBusy(true);
    setVerificationMessage(null);
    setVerificationError(null);
    try {
      const result = await requestEmailVerification();
      setVerificationMessage(result.message);
    } catch (error) {
      setVerificationError(recoveryError(error));
    } finally {
      setVerificationBusy(false);
    }
  }

  async function refreshVerification() {
    setStatusBusy(true);
    setVerificationError(null);
    try {
      setUser(await fetchCurrentUser({ force: true }));
    } catch {
      setVerificationError("Could not refresh your email status. Try again.");
    } finally {
      setStatusBusy(false);
    }
  }
  if (!completion && (bootstrapping || !token))
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
            {!completion && (
              <Link href="/dashboard" className="hover:underline">
                Back to workspace
              </Link>
            )}
          </nav>
        </header>
        <p className="mt-10 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
          Account / sign-in methods
        </p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight">Your account</h1>
        {completion ? (
          <div className="mt-7 border border-stone-300 bg-white p-6">
            <p role="status" className="text-sm leading-relaxed">
              {completion}
            </p>
            <Link href="/login" className={`mt-5 block text-sm ${recoveryLinkClass}`}>
              Go to login
            </Link>
            <Link href="/" className={`mt-4 block text-sm ${recoveryLinkClass}`}>
              Back to website
            </Link>
          </div>
        ) : (
          <>
            <section
              aria-labelledby="email-status-heading"
              className="mt-6 border-b border-stone-300 pb-6"
            >
              <h2 id="email-status-heading" className="text-xl">
                Email verification
              </h2>
              {user ? (
                <>
                  <p className="mt-3 break-all text-sm text-slate-600">{user.email}</p>
                  <p role="status" className="mt-2 font-medium">
                    {user.email_verified ? "Email verified" : "Email not verified"}
                  </p>
                </>
              ) : (
                <p role="status" className="mt-3 text-sm">
                  Could not load your email status.
                </p>
              )}
              {user && !user.email_verified && (
                <>
                  <p className="my-4 text-sm leading-relaxed text-slate-600">
                    Request a verification email, then follow its instructions to confirm
                    your address. Email delivery must be configured for messages to
                    arrive.
                  </p>
                  <button
                    type="button"
                    onClick={() => void sendVerification()}
                    disabled={verificationBusy}
                    className={recoveryButtonClass}
                  >
                    {verificationBusy && (
                      <span aria-hidden="true">
                        <Spinner />
                      </span>
                    )}
                    {verificationBusy
                      ? "Requesting email…"
                      : verificationMessage
                        ? "Resend verification email"
                        : "Send verification email"}
                  </button>
                  <Link
                    href="/verify-email"
                    className={`mt-4 inline-block text-sm ${recoveryLinkClass}`}
                  >
                    Have a code from an older email?
                  </Link>
                </>
              )}
              {(!user || !user.email_verified) && (
                <button
                  type="button"
                  onClick={() => void refreshVerification()}
                  disabled={statusBusy}
                  className={`mt-4 block text-sm ${recoveryLinkClass} disabled:opacity-60`}
                >
                  {statusBusy ? "Checking status…" : "Refresh verification status"}
                </button>
              )}
              {verificationMessage && (
                <p role="status" className="mt-4 text-sm leading-relaxed">
                  {verificationMessage}
                </p>
              )}
              {verificationError && (
                <p role="alert" className="mt-4 text-sm text-rose-700">
                  {verificationError}
                </p>
              )}
            </section>
            {connectionsBusy ? (
              <p role="status" className="mt-7 text-sm">
                Loading sign-in methods…
              </p>
            ) : connectionsError ? (
              <div className="mt-7">
                <p role="alert" className="text-sm text-rose-700">
                  {connectionsError}
                </p>
                <button
                  type="button"
                  className={`mt-4 text-sm ${recoveryLinkClass}`}
                  onClick={() => {
                    setConnectionsBusy(true);
                    setConnectionsError(null);
                    setConnectionsAttempt((value) => value + 1);
                  }}
                >
                  Retry sign-in methods
                </button>
              </div>
            ) : (
              connections &&
              (connections.password || connections.google) && (
                <PasswordManagement
                  hasPassword={connections.password}
                  onComplete={passwordComplete}
                />
              )
            )}
            <h2 className="mt-6 text-xl">Google sign-in</h2>
            {connections?.google ? (
              <p className="mt-3">Google is linked to your account.</p>
            ) : connections?.password ? (
              <>
                <p className="my-4 text-slate-600">
                  Confirm your password, then select the Google account with the same
                  email. Your articles stay in this account.
                </p>
                <label htmlFor="link-password">Current password to link Google</label>
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
          </>
        )}
      </div>
    </main>
  );
}
