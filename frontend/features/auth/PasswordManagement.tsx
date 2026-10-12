"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { addPassword, changePassword, passwordAddChallenge } from "@/lib/api/auth";
import { clearAccessToken } from "@/lib/auth/token-store";
import { isApiError } from "@/lib/api/errors";
import GoogleSignIn from "./GoogleSignIn";
import { strongPasswordSchema } from "./password-schema";
import {
  recoveryButtonClass,
  recoveryInputClass,
  recoveryLinkClass,
} from "./RecoveryShell";

const passwordSchema = z
  .object({
    currentPassword: z.string(),
    password: strongPasswordSchema,
    confirmPassword: z.string(),
  })
  .refine((values) => values.password === values.confirmPassword, {
    message: "Passwords must match",
    path: ["confirmPassword"],
  });
type PasswordValues = z.infer<typeof passwordSchema>;

function passwordError(error: unknown, adding: boolean) {
  if (isApiError(error)) {
    if (error.code === "PASSWORD_CURRENT_INVALID")
      return "Your current password was not accepted. Check it and try again.";
    if (error.code === "PASSWORD_GOOGLE_VERIFICATION_FAILED")
      return "Google verification failed. Select the Google account already linked to SearchScribe and try again.";
    if (error.status === 429)
      return "Too many attempts. Wait a few minutes and try again.";
    if (error.status === 401)
      return "Your session expired. Sign in again before updating your password.";
    if (error.status === 422) return "Check the password requirements and try again.";
    if (error.status === 409)
      return "Your sign-in methods changed. Reload your account page before continuing.";
    if (error.status === 400 || error.status === 403)
      return adding
        ? "Google verification failed. Select the Google account already linked to SearchScribe and try again."
        : "Your current password was not accepted. Check it and try again.";
  }
  return "Could not update your password. Check your connection and try again.";
}

export default function PasswordManagement({
  hasPassword,
  onComplete,
}: {
  hasPassword: boolean;
  onComplete: (message: string) => void;
}) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showPasswords, setShowPasswords] = useState(false);
  const [googleStep, setGoogleStep] = useState(false);
  const active = useRef(false);
  const submitting = useRef(false);
  const revision = useRef(0);
  const preparedPassword = useRef<string | null>(null);
  const form = useForm<PasswordValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { currentPassword: "", password: "", confirmPassword: "" },
  });

  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
      preparedPassword.current = null;
      form.reset();
    };
  }, [form]);

  function editPasswords() {
    if (submitting.current) return;
    revision.current++;
    preparedPassword.current = null;
    setGoogleStep(false);
    setError(null);
  }

  async function mutate(values: PasswordValues, credential?: string) {
    if (submitting.current || !active.current) return;
    const currentRevision = revision.current;
    submitting.current = true;
    setBusy(true);
    setError(null);
    try {
      if (hasPassword) await changePassword(values.currentPassword, values.password);
      else if (credential) await addPassword(credential, values.password);
      else return;
      const message = hasPassword
        ? "Password updated. Sign in again with your new password."
        : "Password added. Sign in again with your new password. Google sign-in is still available.";
      preparedPassword.current = null;
      form.reset();
      // Mark completion before clearing the token so the protected page keeps
      // its confirmation visible instead of immediately redirecting to login.
      if (active.current && revision.current === currentRevision) onComplete(message);
      queryClient.clear();
      clearAccessToken();
    } catch (failure) {
      if (active.current && revision.current === currentRevision)
        setError(passwordError(failure, !hasPassword));
    } finally {
      submitting.current = false;
      if (active.current && revision.current === currentRevision) setBusy(false);
    }
  }

  async function submit(values: PasswordValues) {
    if (submitting.current || !active.current) return;
    if (hasPassword) {
      if (!values.currentPassword) {
        form.setError(
          "currentPassword",
          { message: "Enter your current password" },
          { shouldFocus: true },
        );
        return;
      }
      await mutate(values);
    } else {
      preparedPassword.current = values.password;
      setError(null);
      setGoogleStep(true);
    }
  }

  return (
    <section
      aria-labelledby="password-heading"
      className="mt-7 border-b border-stone-300 pb-7"
    >
      <h2 id="password-heading" className="text-xl">
        {hasPassword ? "Change password" : "Add a password"}
      </h2>
      <p className="my-4 text-sm leading-relaxed text-slate-600">
        {hasPassword
          ? "Your current password cannot be viewed. Enter it below to choose a new one. This signs you out on all devices."
          : "You created this account with Google, so it has no password yet. Choose one, then confirm the same Google account. Your articles and Google sign-in stay available."}
      </p>
      <form
        method="post"
        noValidate
        onSubmit={(event) => void form.handleSubmit(submit)(event)}
        className="space-y-4"
      >
        {hasPassword && (
          <div>
            <label htmlFor="account-current-password" className="mb-1 block text-sm">
              Current password
            </label>
            <input
              id="account-current-password"
              type={showPasswords ? "text" : "password"}
              autoComplete="current-password"
              className={recoveryInputClass}
              disabled={busy}
              aria-invalid={!!form.formState.errors.currentPassword}
              aria-describedby={
                form.formState.errors.currentPassword
                  ? "account-current-password-error"
                  : undefined
              }
              {...form.register("currentPassword")}
              onChange={(event) => {
                void form.register("currentPassword").onChange(event);
                editPasswords();
              }}
            />
            {form.formState.errors.currentPassword && (
              <p
                id="account-current-password-error"
                role="alert"
                className="mt-1 text-sm text-rose-700"
              >
                {form.formState.errors.currentPassword.message}
              </p>
            )}
          </div>
        )}
        <div>
          <label htmlFor="account-new-password" className="mb-1 block text-sm">
            New password
          </label>
          <input
            id="account-new-password"
            type={showPasswords ? "text" : "password"}
            autoComplete="new-password"
            className={recoveryInputClass}
            disabled={busy}
            aria-invalid={!!form.formState.errors.password}
            aria-describedby={`account-password-help${form.formState.errors.password ? " account-new-password-error" : ""}`}
            {...form.register("password")}
              onChange={(event) => {
                void form.register("password").onChange(event);
                editPasswords();
              }}
          />
          <p id="account-password-help" className="mt-2 text-xs text-slate-600">
            Use 8–128 characters, including a letter and a digit.
          </p>
          {form.formState.errors.password && (
            <p
              id="account-new-password-error"
              role="alert"
              className="mt-1 text-sm text-rose-700"
            >
              {form.formState.errors.password.message}
            </p>
          )}
        </div>
        <div>
          <label htmlFor="account-confirm-password" className="mb-1 block text-sm">
            Confirm new password
          </label>
          <input
            id="account-confirm-password"
            type={showPasswords ? "text" : "password"}
            autoComplete="new-password"
            className={recoveryInputClass}
            disabled={busy}
            aria-invalid={!!form.formState.errors.confirmPassword}
            aria-describedby={
              form.formState.errors.confirmPassword
                ? "account-confirm-password-error"
                : undefined
            }
            {...form.register("confirmPassword")}
              onChange={(event) => {
                void form.register("confirmPassword").onChange(event);
                editPasswords();
              }}
          />
          {form.formState.errors.confirmPassword && (
            <p
              id="account-confirm-password-error"
              role="alert"
              className="mt-1 text-sm text-rose-700"
            >
              {form.formState.errors.confirmPassword.message}
            </p>
          )}
        </div>
        <button
          type="button"
          aria-pressed={showPasswords}
          onClick={() => setShowPasswords(!showPasswords)}
          className={`text-sm ${recoveryLinkClass}`}
        >
          {showPasswords ? "Hide entered passwords" : "Show entered passwords"}
        </button>
        {error && (
          <p role="alert" className="text-sm text-rose-700">
            {error}
          </p>
        )}
        {error?.startsWith("Your session expired") && (
          <Link href="/login" className={`block text-sm ${recoveryLinkClass}`}>
            Sign in again
          </Link>
        )}
        {!googleStep && (
          <button type="submit" disabled={busy} className={recoveryButtonClass}>
            {busy
              ? "Updating password…"
              : hasPassword
                ? "Change password"
                : "Continue with Google"}
          </button>
        )}
        {hasPassword && (
          <Link href="/forgot-password" className={`block text-sm ${recoveryLinkClass}`}>
            Forgot your current password?
          </Link>
        )}
      </form>
      {googleStep && (
        <div className="mt-5 border-t border-stone-200 pt-4">
          <p className="text-sm leading-relaxed">
            Confirm your linked Google account to add this password. This signs you out on
            all devices.
          </p>
          <GoogleSignIn
            challengeLoader={passwordAddChallenge}
            showUnavailableMessage
            unavailableMessage="Google verification is unavailable on this instance. Continue using Google sign-in; your account has not changed."
            failureMessage="Google verification could not load. Retry the Google connection. Your account has not changed."
            verificationLabel="Confirming Google and adding password…"
            onError={setError}
            onCredential={async (credential) => {
              const password = preparedPassword.current;
              if (!password || !active.current) return;
              await mutate({ ...form.getValues(), password }, credential);
            }}
          />
          {busy && (
            <p role="status" className="text-sm">
              Adding password…
            </p>
          )}
        </div>
      )}
    </section>
  );
}
