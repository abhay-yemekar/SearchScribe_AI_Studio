"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowLeft, Sparkles, FileText, Code2, Search } from "lucide-react";
import Link from "next/link";

import { googleLogin, login, signup } from "@/lib/api/auth";
import GoogleSignIn from "./GoogleSignIn";
import { isApiError } from "@/lib/api/errors";
import { Spinner } from "@/components/shared/States";
import BrandLogo from "@/components/brand/BrandLogo";

const authSchema = z.object({
  name: z.string().trim().min(1, "Name is required").max(100),
  email: z.string().email("Enter a valid email"),
  password: z
    .string()
    .min(8, "At least 8 characters")
    .regex(/[A-Za-z]/, "Include a letter")
    .regex(/\d/, "Include a digit"),
});

const loginSchema = authSchema.omit({ name: true });

type SignupValues = z.infer<typeof authSchema>;
export default function AuthForm({
  initialMode = "login",
}: {
  initialMode?: "login" | "signup";
}) {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">(initialMode);
  const [serverError, setServerError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isSignup = mode === "signup";

  const form = useForm<SignupValues & { name?: string }>({
    resolver: zodResolver(isSignup ? authSchema : (loginSchema as never)),
    defaultValues: { name: "", email: "", password: "" },
  });

  const onSubmit = async (values: SignupValues & { name?: string }) => {
    setServerError(null);
    setBusy(true);
    try {
      if (isSignup) {
        await signup({
          name: values.name ?? "",
          email: values.email,
          password: values.password,
        });
      } else {
        await login({ email: values.email, password: values.password });
      }
      router.push("/dashboard");
    } catch (error) {
      if (isApiError(error)) {
        setServerError(error.message);
      } else if (error instanceof z.ZodError) {
        setServerError(error.issues[0]?.message ?? "Invalid input");
      } else {
        setServerError("Cannot reach the server. Is the backend running?");
      }
    } finally {
      setBusy(false);
    }
  };

  const fieldClass =
    "w-full rounded-lg border border-stone-300 bg-white px-3 py-3 text-sm text-[#17252b] outline-none transition-colors focus:border-[#17252b] focus-visible:ring-2 focus-visible:ring-[#17252b]/20";

  return (
    <div className="login-shell min-h-screen bg-[#f4f5f1] px-5 py-8 text-[#17252b] sm:px-8 sm:py-10">
      <div className="mx-auto w-full max-w-6xl">
        <header className="login-header flex flex-col items-start gap-5 border-b border-stone-300 pb-6 sm:flex-row sm:items-center sm:justify-between">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm font-semibold hover:underline"
          >
            <ArrowLeft aria-hidden className="h-4 w-4" /> Back to SearchScribe
          </Link>
          <BrandLogo />
        </header>
        <div className="login-layout grid items-start gap-10 py-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,28rem)] lg:gap-16 lg:py-14">
          {/* Hero */}
          <section className="order-2 min-w-0 lg:order-1">
            <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
              Your words. Your workspace.
            </p>
            <h1 className="text-4xl font-semibold leading-[1.08] tracking-tight md:text-5xl">
              Welcome to <span>SearchScribe</span>
            </h1>
            <p className="mt-3 text-xl font-light leading-relaxed text-slate-600">
              Make a first draft, find your own voice, and shape the details before
              exporting your article.
            </p>

            <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="rounded-xl border border-stone-300 bg-white p-5">
                <p className="mb-1 text-xs uppercase tracking-wide text-slate-600">
                  AI Content Studio
                </p>
                <p className="text-sm text-slate-700">
                  One query becomes a structured article, SEO metadata, and a standalone
                  HTML page.
                </p>
              </div>
              <div className="rounded-xl border border-stone-300 bg-white p-5">
                <p className="mb-2 text-xs uppercase tracking-wide text-slate-600">
                  What you get
                </p>
                <ul className="space-y-2 text-sm text-slate-700">
                  <li className="flex items-center gap-2">
                    <FileText aria-hidden className="h-4 w-4 shrink-0" /> Full article
                    with version history
                  </li>
                  <li className="flex items-center gap-2">
                    <Search aria-hidden className="h-4 w-4 shrink-0" /> SEO title,
                    description, keywords
                  </li>
                  <li className="flex items-center gap-2">
                    <Code2 aria-hidden className="h-4 w-4 shrink-0" /> Sanitized,
                    downloadable HTML
                  </li>
                  <li className="flex items-center gap-2">
                    <Sparkles aria-hidden className="h-4 w-4 shrink-0" /> Six rewrite
                    styles, one click
                  </li>
                </ul>
              </div>
            </div>
          </section>

          {/* Auth card */}
          <section className="order-1 mx-auto w-full max-w-md min-w-0 lg:order-2 lg:mx-0">
            <div className="login-panel rounded-xl border border-stone-300 bg-white p-6 md:p-8">
              <h2 className="mb-1 text-center text-xl font-semibold">
                {isSignup ? "Create account" : "Login"}
              </h2>
              <p className="mb-5 text-center text-xs text-slate-600">
                {isSignup
                  ? "Sign up to start generating AI-powered content."
                  : "Sign in to continue using SearchScribe."}
              </p>

              <GoogleSignIn
                showUnavailableMessage
                onError={setServerError}
                onCredential={async (credential) => {
                  setServerError(null);
                  await googleLogin(credential);
                  router.push("/dashboard");
                }}
              />
              <form
                onSubmit={form.handleSubmit(onSubmit)}
                className="space-y-4"
                noValidate
              >
                {isSignup && (
                  <div>
                    <label htmlFor="name" className="mb-1 block text-xs text-slate-700">
                      Name
                    </label>
                    <input
                      id="name"
                      type="text"
                      autoComplete="name"
                      className={fieldClass}
                      placeholder="Your name"
                      aria-invalid={!!form.formState.errors.name}
                      {...form.register("name")}
                    />
                    {form.formState.errors.name && (
                      <p role="alert" className="mt-1 text-xs text-rose-700">
                        {form.formState.errors.name.message}
                      </p>
                    )}
                  </div>
                )}

                <div>
                  <label htmlFor="email" className="mb-1 block text-xs text-slate-700">
                    Email
                  </label>
                  <input
                    id="email"
                    type="email"
                    autoComplete="email"
                    className={fieldClass}
                    placeholder="you@example.com"
                    aria-invalid={!!form.formState.errors.email}
                    {...form.register("email")}
                  />
                  {form.formState.errors.email && (
                    <p role="alert" className="mt-1 text-xs text-rose-700">
                      {form.formState.errors.email.message}
                    </p>
                  )}
                </div>

                <div>
                  <label htmlFor="password" className="mb-1 block text-xs text-slate-700">
                    Password
                  </label>
                  <input
                    id="password"
                    type="password"
                    autoComplete={isSignup ? "new-password" : "current-password"}
                    className={fieldClass}
                    placeholder="••••••••"
                    aria-invalid={!!form.formState.errors.password}
                    {...form.register("password")}
                  />
                  {form.formState.errors.password && (
                    <p role="alert" className="mt-1 text-xs text-rose-700">
                      {form.formState.errors.password.message}
                    </p>
                  )}
                </div>

                {serverError && (
                  <p role="alert" className="text-xs text-rose-700">
                    {serverError}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={busy}
                  className="studio-primary-action mt-2 flex w-full items-center justify-center gap-2 rounded-lg bg-[#17252b] py-3 text-sm font-semibold text-white transition-colors hover:bg-[#293f48] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {busy ? <Spinner /> : null}
                  {busy ? "Please wait…" : isSignup ? "Sign up" : "Login"}
                </button>
              </form>

              <div className="mt-4 text-center">
                <button
                  type="button"
                  onClick={() => {
                    setServerError(null);
                    setMode(isSignup ? "login" : "signup");
                  }}
                  className="text-xs text-slate-600 transition-colors hover:text-[#17252b] hover:underline"
                >
                  {isSignup
                    ? "Already have an account? Login"
                    : "Don't have an account? Sign up"}
                </button>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
