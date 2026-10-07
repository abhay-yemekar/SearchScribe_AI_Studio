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
    "w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition-colors focus:border-teal-700 focus-visible:ring-2 focus-visible:ring-teal-700/30";

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f5f3ee] px-4 py-10 text-slate-900">
      <div className="flex w-full max-w-5xl flex-col items-center gap-10 md:flex-row md:px-8">
        {/* Hero */}
        <section className="fade-in-up flex-1">
          <Link
            href="/"
            className="mb-8 inline-flex items-center gap-2 text-sm font-semibold text-teal-800 hover:underline"
          >
            <ArrowLeft aria-hidden className="h-4 w-4" /> Back to SearchScribe
          </Link>
          <h1 className="font-serif text-4xl leading-tight md:text-5xl">
            Welcome to <span className="text-teal-800">SearchScribe</span>
          </h1>
          <p className="mt-3 text-xl font-light leading-relaxed text-slate-600">
            Create SEO-optimized articles and ready-to-publish HTML —{" "}
            <span className="font-medium text-teal-800">all from one topic.</span>
          </p>

          <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="rounded-2xl border border-stone-300 bg-[#e7e9e2] p-4">
              <p className="mb-1 text-xs uppercase tracking-wide text-slate-600">
                AI Content Studio
              </p>
              <p className="text-sm text-slate-700">
                One query becomes a structured article, SEO metadata, and a standalone
                HTML page.
              </p>
            </div>
            <div className="rounded-2xl border border-stone-300 bg-white p-4">
              <p className="mb-2 text-xs uppercase tracking-wide text-slate-600">
                What you get
              </p>
              <ul className="space-y-2 text-sm text-slate-700">
                <li className="flex items-center gap-2">
                  <FileText aria-hidden className="h-4 w-4 text-teal-800" /> Full article
                  with version history
                </li>
                <li className="flex items-center gap-2">
                  <Search aria-hidden className="h-4 w-4 text-teal-800" /> SEO title,
                  description, keywords
                </li>
                <li className="flex items-center gap-2">
                  <Code2 aria-hidden className="h-4 w-4 text-teal-800" /> Sanitized,
                  downloadable HTML
                </li>
                <li className="flex items-center gap-2">
                  <Sparkles aria-hidden className="h-4 w-4 text-teal-800" /> Six rewrite
                  styles, one click
                </li>
              </ul>
            </div>
          </div>
        </section>

        {/* Auth card */}
        <section className="fade-in-right w-full max-w-md flex-1">
          <div className="rounded-2xl border border-stone-300 bg-white p-6 shadow-xl md:p-8">
            <h2 className="mb-1 text-center text-xl font-semibold">
              {isSignup ? "Create account" : "Login"}
            </h2>
            <p className="mb-5 text-center text-xs text-slate-600">
              {isSignup
                ? "Sign up to start generating AI-powered content."
                : "Sign in to continue using SearchScribe."}
            </p>

            <GoogleSignIn
              onError={setServerError}
              onCredential={async (credential) => {
                setServerError(null);
                await googleLogin(credential);
                router.push("/dashboard");
              }}
            />
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
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
                    <p role="alert" className="mt-1 text-xs text-rose-400">
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
                  <p role="alert" className="mt-1 text-xs text-rose-400">
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
                  <p role="alert" className="mt-1 text-xs text-rose-400">
                    {form.formState.errors.password.message}
                  </p>
                )}
              </div>

              {serverError && (
                <p role="alert" className="text-xs text-rose-400">
                  {serverError}
                </p>
              )}

              <button
                type="submit"
                disabled={busy}
                className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg bg-teal-800 py-2.5 text-sm font-medium text-white transition-colors hover:bg-teal-900 disabled:cursor-not-allowed disabled:opacity-60"
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
                className="text-xs text-slate-600 transition-colors hover:text-teal-800"
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
  );
}
