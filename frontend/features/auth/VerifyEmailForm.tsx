"use client";

import { useState } from "react";
import Link from "next/link";
import { verifyEmail } from "@/lib/api/auth";
import { isApiError } from "@/lib/api/errors";
import { Spinner } from "@/components/shared/States";
import RecoveryShell, {
  recoveryButtonClass,
  recoveryInputClass,
  recoveryLinkClass,
} from "./RecoveryShell";
import { recoveryError } from "./recovery-errors";
import { useFragmentToken } from "./useFragmentToken";

export default function VerifyEmailForm() {
  const link = useFragmentToken();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [codeError, setCodeError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function submit() {
    const token = link.getToken() ?? code.trim();
    if (busy) return;
    if (!token || token.length > 512) {
      setCodeError("Paste the full verification code from your email");
      return;
    }
    setBusy(true);
    setError(null);
    setCodeError(null);
    try {
      await verifyEmail(token);
      link.discardToken();
      setCode("");
      setDone(true);
    } catch (failure) {
      if (isApiError(failure) && [400, 410].includes(failure.status)) {
        link.discardToken();
        setCode("");
        setError(
          "This verification code is invalid, expired, or already used. Request a new code from your account and try again.",
        );
      } else {
        setError(recoveryError(failure));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <RecoveryShell
      title="Verify your email"
      description="Copy the verification code from your security email to confirm your SearchScribe account."
    >
      {done ? (
        <p role="status" className="text-sm leading-relaxed">
          Your email is verified. You can return to your account.
        </p>
      ) : link.status === "loading" ? (
        <p role="status">Opening verification link…</p>
      ) : (
        <form
          method="post"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
          className="space-y-4"
          noValidate
        >
          {link.status === "missing" && (
            <div>
              <label htmlFor="verification-code" className="mb-1 block text-sm">
                Verification code
              </label>
              <input
                id="verification-code"
                type="password"
                autoComplete="off"
                autoCapitalize="none"
                spellCheck={false}
                className={recoveryInputClass}
                value={code}
                onChange={(event) => setCode(event.target.value)}
                aria-invalid={!!codeError}
                aria-describedby={codeError ? "verification-code-error" : undefined}
              />
              {codeError && (
                <p
                  id="verification-code-error"
                  role="alert"
                  className="mt-1 text-sm text-rose-700"
                >
                  {codeError}
                </p>
              )}
            </div>
          )}
          {error && (
            <p role="alert" className="text-sm text-rose-700">
              {error}
            </p>
          )}
          <button type="submit" disabled={busy} className={recoveryButtonClass}>
            {busy && (
              <span aria-hidden="true">
                <Spinner />
              </span>
            )}
            {busy ? "Verifying email…" : "Verify email"}
          </button>
          <p className="text-xs leading-relaxed text-slate-600">
            Need a new code? Sign in and request one from your account.
          </p>
        </form>
      )}
      <Link href="/account" className={`mt-5 block text-sm ${recoveryLinkClass}`}>
        {done ? "Go to account" : "Sign in or open your account"}
      </Link>
    </RecoveryShell>
  );
}
