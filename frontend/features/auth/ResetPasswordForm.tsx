"use client";

import { useState } from "react";
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
import { useFragmentToken } from "./useFragmentToken";

export default function ResetPasswordForm() {
  const link = useFragmentToken();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const form = useForm<z.infer<typeof resetPasswordSchema>>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { password: "", confirmPassword: "", code: "" },
  });

  async function submit(values: z.infer<typeof resetPasswordSchema>) {
    const token = link.getToken() ?? values.code;
    if (!token) {
      form.setError(
        "code",
        { message: "Paste the reset code from your email" },
        { shouldFocus: true },
      );
      return;
    }
    setError(null);
    try {
      await resetPassword(token, values.password);
      link.discardToken();
      queryClient.clear();
      form.reset();
      setDone(true);
    } catch (failure) {
      if (isApiError(failure) && [400, 410].includes(failure.status)) {
        link.discardToken();
        form.setValue("code", "");
        setError(
          "This reset code is invalid, expired, or already used. Request a new code and try again.",
        );
      } else {
        setError(recoveryError(failure));
      }
    }
  }

  return (
    <RecoveryShell
      title="Reset your password"
      description="Copy the reset code from your security email, then choose a new password."
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
      ) : (
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
                Paste the full code from your password reset email.
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
          <button
            type="submit"
            disabled={form.formState.isSubmitting}
            className={recoveryButtonClass}
          >
            {form.formState.isSubmitting && (
              <span aria-hidden="true">
                <Spinner />
              </span>
            )}
            {form.formState.isSubmitting ? "Resetting password…" : "Reset password"}
          </button>
          <Link href="/forgot-password" className={`block text-sm ${recoveryLinkClass}`}>
            Request a new reset code
          </Link>
        </form>
      )}
    </RecoveryShell>
  );
}
