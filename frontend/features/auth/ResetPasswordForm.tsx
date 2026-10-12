"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { resetPassword } from "@/lib/api/auth";
import { isApiError } from "@/lib/api/errors";
import { Spinner } from "@/components/shared/States";
import RecoveryShell, {
  recoveryButtonClass,
  recoveryInputClass,
  recoveryLinkClass,
} from "./RecoveryShell";
import { resetPasswordSchema } from "./password-schema";
import { recoveryError } from "./recovery-errors";
import { isRecoveryToken, useFragmentToken } from "./useFragmentToken";

export default function ResetPasswordForm() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [legacyOpen, setLegacyOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const invalidLinkAction = useRef<HTMLAnchorElement>(null);
  const form = useForm<z.infer<typeof resetPasswordSchema>>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { password: "", confirmPassword: "", code: "" },
  });
  const link = useFragmentToken(() => {
    setDone(false);
    setError(null);
    setLegacyOpen(false);
    setBusy(false);
    form.reset();
  });

  useEffect(() => {
    if (link.status === "invalid") invalidLinkAction.current?.focus();
  }, [link.status]);

  async function submit(values: z.infer<typeof resetPasswordSchema>) {
    const currentRevision = link.revision;
    if (busy || !link.isCurrent(currentRevision)) return;
    const token = link.getToken() ?? values.code;
    const fromLink = link.status === "ready";
    if (!isRecoveryToken(token)) {
      form.setError(
        "code",
        {
          message: "Paste the complete code from your older email, or request a new link",
        },
        { shouldFocus: true },
      );
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await resetPassword(token, values.password);
      queryClient.clear();
      if (!link.isCurrent(currentRevision)) return;
      link.discardToken(currentRevision);
      form.reset();
      setDone(true);
    } catch (failure) {
      if (!link.isCurrent(currentRevision)) return;
      const tokenValidationFailure =
        isApiError(failure) &&
        failure.status === 422 &&
        failure.details?.fields?.some(({ field }) => field.split(".").at(-1) === "token");
      if (
        isApiError(failure) &&
        ([400, 410].includes(failure.status) || tokenValidationFailure)
      ) {
        if (fromLink) {
          link.discardToken(currentRevision, "invalid");
          form.reset();
        } else {
          form.setValue("code", "");
          form.setError(
            "code",
            {
              message:
                "This code is invalid, expired, or already used. Request a new reset link.",
            },
            { shouldFocus: true },
          );
        }
      } else if (isApiError(failure) && failure.status === 422) {
        setError(
          "The new password was not accepted. Check the password requirements and try again.",
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
      title="Reset your password"
      description={
        link.status === "ready"
          ? "Choose a new password below. Select Reset password to finish."
          : "Follow the reset instructions in your security email."
      }
    >
      {done ? (
        <div role="status">
          <p className="text-sm leading-relaxed">
            Your password has been reset. Sign in again with your new password.
          </p>
          <Link href="/login" className={`mt-5 block text-sm ${recoveryLinkClass}`}>
            Go to login
          </Link>
        </div>
      ) : link.status === "loading" ? (
        <p role="status">Opening reset link…</p>
      ) : link.status === "invalid" ? (
        <div>
          <p role="alert" className="text-sm leading-relaxed">
            This reset link is invalid, expired, or already used. Request a new link to
            continue.
          </p>
          <Link
            ref={invalidLinkAction}
            href="/forgot-password"
            className={`mt-5 block text-sm ${recoveryLinkClass}`}
          >
            Request a new reset link
          </Link>
        </div>
      ) : (
        <>
          {link.status === "missing" && (
            <div>
              <p role="status" className="text-sm leading-relaxed">
                Open the reset link from your security email. If your email contains a
                code instead, use the option below.
              </p>
              <Link
                href="/forgot-password"
                className={`mt-5 block text-sm ${recoveryLinkClass}`}
              >
                Request a new reset link
              </Link>
              <button
                type="button"
                aria-expanded={legacyOpen}
                aria-controls="legacy-reset-form"
                onClick={() => setLegacyOpen(!legacyOpen)}
                className={`mt-5 text-sm ${recoveryLinkClass}`}
              >
                Have a code from an older email?
              </button>
            </div>
          )}
          <div
            id="legacy-reset-form"
            hidden={link.status === "missing" && !legacyOpen}
            className={link.status === "missing" ? "mt-5" : undefined}
          >
            <form
              method="post"
              onSubmit={form.handleSubmit(submit)}
              className="space-y-4"
              noValidate
            >
              {link.status === "missing" && (
                <div>
                  <label htmlFor="reset-code" className="mb-1 block text-sm">
                    Reset code
                  </label>
                  <input
                    id="reset-code"
                    type="password"
                    autoComplete="off"
                    autoCapitalize="none"
                    spellCheck={false}
                    className={recoveryInputClass}
                    aria-invalid={!!form.formState.errors.code}
                    aria-describedby={`reset-code-help${form.formState.errors.code ? " reset-code-error" : ""}`}
                    {...form.register("code")}
                  />
                  <p id="reset-code-help" className="mt-2 text-xs text-slate-600">
                    Paste the full code from your older password reset email.
                  </p>
                  {form.formState.errors.code && (
                    <p
                      id="reset-code-error"
                      role="alert"
                      className="mt-1 text-sm text-rose-700"
                    >
                      {form.formState.errors.code.message}
                    </p>
                  )}
                </div>
              )}
              <div>
                <label htmlFor="new-password" className="mb-1 block text-sm">
                  New password
                </label>
                <input
                  id="new-password"
                  type="password"
                  autoComplete="new-password"
                  className={recoveryInputClass}
                  aria-invalid={!!form.formState.errors.password}
                  aria-describedby={`password-help${form.formState.errors.password ? " new-password-error" : ""}`}
                  {...form.register("password")}
                />
                <p id="password-help" className="mt-2 text-xs text-slate-600">
                  Use 8–128 characters, including a letter and a digit.
                </p>
                {form.formState.errors.password && (
                  <p
                    id="new-password-error"
                    role="alert"
                    className="mt-1 text-sm text-rose-700"
                  >
                    {form.formState.errors.password.message}
                  </p>
                )}
              </div>
              <div>
                <label htmlFor="confirm-password" className="mb-1 block text-sm">
                  Repeat new password
                </label>
                <input
                  id="confirm-password"
                  type="password"
                  autoComplete="new-password"
                  className={recoveryInputClass}
                  aria-invalid={!!form.formState.errors.confirmPassword}
                  aria-describedby={
                    form.formState.errors.confirmPassword
                      ? "confirm-password-error"
                      : undefined
                  }
                  {...form.register("confirmPassword")}
                />
                {form.formState.errors.confirmPassword && (
                  <p
                    id="confirm-password-error"
                    role="alert"
                    className="mt-1 text-sm text-rose-700"
                  >
                    {form.formState.errors.confirmPassword.message}
                  </p>
                )}
              </div>
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
                {busy ? "Resetting password…" : "Reset password"}
              </button>
              {link.status === "ready" && (
                <Link
                  href="/forgot-password"
                  className={`block text-sm ${recoveryLinkClass}`}
                >
                  Request a new reset link
                </Link>
              )}
            </form>
          </div>
        </>
      )}
    </RecoveryShell>
  );
}
