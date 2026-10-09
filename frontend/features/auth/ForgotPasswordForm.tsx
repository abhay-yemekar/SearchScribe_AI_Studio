"use client";

import { useState } from "react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { forgotPassword } from "@/lib/api/auth";
import { Spinner } from "@/components/shared/States";
import { useHydrated } from "@/lib/useHydrated";
import RecoveryShell, {
  recoveryButtonClass,
  recoveryInputClass,
  recoveryLinkClass,
} from "./RecoveryShell";
import { recoveryError } from "./recovery-errors";

const schema = z.object({ email: z.string().trim().email("Enter a valid email") });

export default function ForgotPasswordForm() {
  const hydrated = useHydrated();
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { email: "" },
  });

  async function submit(values: z.infer<typeof schema>) {
    setError(null);
    setMessage(null);
    try {
      const result = await forgotPassword(values.email);
      setMessage(result.message);
    } catch (failure) {
      setError(recoveryError(failure));
    }
  }

  return (
    <RecoveryShell
      title="Forgot your password?"
      description="Enter your account email to request a password reset code."
    >
      <form
        method="post"
        onSubmit={form.handleSubmit(submit)}
        className="space-y-4"
        noValidate
      >
        <div>
          <label htmlFor="recovery-email" className="mb-1 block text-sm">
            Email
          </label>
          <input
            id="recovery-email"
            type="email"
            autoComplete="email"
            disabled={!hydrated}
            className={recoveryInputClass}
            aria-invalid={!!form.formState.errors.email}
            aria-describedby={
              form.formState.errors.email ? "recovery-email-error" : undefined
            }
            {...form.register("email")}
          />
          {form.formState.errors.email && (
            <p
              id="recovery-email-error"
              role="alert"
              className="mt-1 text-sm text-rose-700"
            >
              {form.formState.errors.email.message}
            </p>
          )}
        </div>
        {error && (
          <p role="alert" className="text-sm text-rose-700">
            {error}
          </p>
        )}
        {message && (
          <p role="status" className="text-sm leading-relaxed">
            {message}
          </p>
        )}
        <button
          type="submit"
          disabled={!hydrated || form.formState.isSubmitting}
          className={recoveryButtonClass}
        >
          {form.formState.isSubmitting && (
            <span aria-hidden="true">
              <Spinner />
            </span>
          )}
          {form.formState.isSubmitting
            ? "Requesting code…"
            : message
              ? "Request another code"
              : "Request reset code"}
        </button>
      </form>
      <p className="mt-5 text-sm leading-relaxed text-slate-600">
        If you signed up with Google, use Google sign-in on the{" "}
        <Link href="/login" className={recoveryLinkClass}>
          login page
        </Link>
        .
      </p>
      <p className="mt-3 text-xs leading-relaxed text-slate-600">
        For privacy, this request never confirms whether an email has an account. Codes
        are sent only when email delivery is configured.
      </p>
    </RecoveryShell>
  );
}
