"use client";

import { useEffect, useRef, useState } from "react";
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
import { isRecoveryToken, useFragmentToken } from "./useFragmentToken";

export default function VerifyEmailForm() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [codeError, setCodeError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [legacyOpen, setLegacyOpen] = useState(false);
  const invalidLinkAction = useRef<HTMLAnchorElement>(null);
  const link = useFragmentToken(() => {
    setDone(false);
    setError(null);
    setLegacyOpen(false);
    setBusy(false);
    setCode("");
    setCodeError(null);
  });

  useEffect(() => {
    if (link.status === "invalid") invalidLinkAction.current?.focus();
  }, [link.status]);

  async function submit() {
    const currentRevision = link.revision;
    if (busy || !link.isCurrent(currentRevision)) return;
    const token = link.getToken() ?? code.trim();
    const fromLink = link.status === "ready";
    if (!isRecoveryToken(token)) {
      setCodeError(
        "Paste the complete code from your older email, or request a new link",
      );
      return;
    }
    setBusy(true);
    setError(null);
    setCodeError(null);
    try {
      await verifyEmail(token);
      if (!link.isCurrent(currentRevision)) return;
      link.discardToken(currentRevision);
      setCode("");
      setDone(true);
    } catch (failure) {
      if (!link.isCurrent(currentRevision)) return;
      if (isApiError(failure) && [400, 410, 422].includes(failure.status)) {
        if (fromLink) link.discardToken(currentRevision, "invalid");
        setCode("");
        if (!fromLink)
          setCodeError(
            "This code is invalid, expired, or already used. Request a new verification link.",
          );
      } else {
        setError(recoveryError(failure));
      }
    } finally {
      if (link.isCurrent(currentRevision)) setBusy(false);
    }
  }

  return (
    <RecoveryShell
      title="Confirm your email"
      description={
        link.status === "ready"
          ? "Confirm the email address associated with this link using the button below."
          : "Follow the verification instructions in your security email."
      }
    >
      {done ? (
        <p role="status" className="text-sm leading-relaxed">
          Your email is verified. You can return to your account.
        </p>
      ) : link.status === "loading" ? (
        <p role="status">Opening verification link…</p>
      ) : link.status === "invalid" ? (
        <div>
          <p role="alert" className="text-sm leading-relaxed">
            This verification link is invalid, expired, or already used. Request a new
            link from your account.
          </p>
          <Link
            ref={invalidLinkAction}
            href="/account"
            className={`mt-5 block text-sm ${recoveryLinkClass}`}
          >
            Request a new verification link
          </Link>
        </div>
      ) : (
        <>
          {link.status === "missing" && (
            <div>
              <p role="status" className="text-sm leading-relaxed">
                Open the verification link from your security email. If your email
                contains a code instead, use the option below.
              </p>
              <Link href="/account" className={`mt-5 block text-sm ${recoveryLinkClass}`}>
                Request a new verification link
              </Link>
              <button
                type="button"
                aria-expanded={legacyOpen}
                aria-controls="legacy-verification-form"
                onClick={() => setLegacyOpen(!legacyOpen)}
                className={`mt-5 text-sm ${recoveryLinkClass}`}
              >
                Have a code from an older email?
              </button>
            </div>
          )}
          <div
            id="legacy-verification-form"
            hidden={link.status === "missing" && !legacyOpen}
            className={link.status === "missing" ? "mt-5" : undefined}
          >
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
                {busy ? "Confirming email…" : "Confirm email"}
              </button>
              <p className="text-xs leading-relaxed text-slate-600">
                Need a new link? Sign in and request one from your account.
              </p>
            </form>
          </div>
        </>
      )}
      {(done || link.status === "ready") && (
        <Link href="/account" className={`mt-5 block text-sm ${recoveryLinkClass}`}>
          {done ? "Go to account" : "Sign in or open your account"}
        </Link>
      )}
    </RecoveryShell>
  );
}
