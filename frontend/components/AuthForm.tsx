"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type Mode = "login" | "signup";

export default function AuthForm() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleMode = () => {
    setError(null);
    setMode((m) => (m === "login" ? "signup" : "login"));
  };

  const handleLogin = async () => {
    try {
      setError(null);
      setLoading(true);

      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const text = await res.text();
        console.error(text);
        throw new Error("Invalid email or password.");
      }

      const data = await res.json();

      if (typeof window !== "undefined") {
        localStorage.setItem("token", data.access_token);
        const existingName = localStorage.getItem("user_name");
        if (!existingName && name) {
          localStorage.setItem("user_name", name);
        }
      }

      router.push("/dashboard");
    } catch (err: any) {
      console.error(err);
      setError(err?.message || "Login failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleSignup = async () => {
    try {
      setError(null);
      if (!name.trim()) {
        setError("Please enter your name.");
        return;
      }

      setLoading(true);

      const res = await fetch(`${API_BASE}/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const text = await res.text();
        console.error(text);
        throw new Error("Sign up failed. Try another email.");
      }

      if (typeof window !== "undefined") {
        localStorage.setItem("user_name", name);
      }

      await handleLogin();
    } catch (err: any) {
      console.error(err);
      setError(
        err?.message || "Signup failed. Please check your details."
      );
      setLoading(false);
    }
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (mode === "login") {
      await handleLogin();
    } else {
      await handleSignup();
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center">
      <div className="max-w-6xl w-full px-4 md:px-8 py-10 flex flex-col md:flex-row items-center gap-10">
        {/* Left: Hero + illustration */}
        <div className="flex-1 fade-in-up">
          <h1 className="text-3xl md:text-4xl font-bold leading-tight">
            Welcome to{" "}
            <span className="text-blue-400">
              SearchScribe AI Studio
            </span>
          </h1>

          <p className="text-xl text-slate-300 font-light mt-3 leading-relaxed">
            Create SEO-optimized articles and ready-to-publish HTML —{" "}
            <span className="text-blue-400 font-medium">
              all from one search.
            </span>
          </p>

          <p className="text-slate-400 text-sm mt-3">
            By <span className="font-semibold">Abhay Yemekar</span>
          </p>

          {/* Illustration-style block */}
          <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="bg-gradient-to-br from-blue-500/20 to-purple-500/10 border border-slate-700 rounded-2xl p-4 flex flex-col justify-between">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-300 mb-1">
                  AI Content Studio
                </p>
                <p className="text-sm text-slate-200">
                  Turn a single topic into a full article, SEO metadata,
                  and HTML landing page.
                </p>
              </div>
              <div className="mt-4 flex items-center gap-3 text-xs text-slate-300">
                <span className="px-2 py-1 rounded-full bg-slate-900/70 border border-slate-600">
                  Article
                </span>
                <span className="px-2 py-1 rounded-full bg-slate-900/70 border border-slate-600">
                  SEO
                </span>
                <span className="px-2 py-1 rounded-full bg-slate-900/70 border border-slate-600">
                  HTML
                </span>
              </div>
            </div>

            <div className="bg-slate-900/80 border border-slate-700 rounded-2xl p-4 flex flex-col justify-between">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-300 mb-1">
                  Why SearchScribe?
                </p>
                <ul className="text-sm text-slate-200 space-y-1 list-disc list-inside">
                  <li>One query → complete content stack</li>
                  <li>Clean HTML preview & download</li>
                  <li>History & Gen Z re-write in 1 click</li>
                </ul>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Auth card */}
        <div className="flex-1 max-w-md w-full fade-in-right">
          <div className="bg-slate-900/90 border border-slate-700 rounded-2xl shadow-xl p-6 md:p-8">
            <h2 className="text-xl font-semibold text-white mb-1 text-center">
              {mode === "login" ? "Login" : "Create Account"}
            </h2>
            <p className="text-xs text-slate-400 mb-5 text-center">
              {mode === "login"
                ? "Sign in to continue using SearchScribe AI Studio."
                : "Sign up to start generating AI-powered content."}
            </p>

            <form onSubmit={handleSubmit} className="space-y-4">
              {mode === "signup" && (
                <div>
                  <label className="block text-xs mb-1 text-slate-300">
                    Name
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-sm outline-none focus:border-blue-500"
                    placeholder="Your name"
                  />
                </div>
              )}

              <div>
                <label className="block text-xs mb-1 text-slate-300">
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-sm outline-none focus:border-blue-500"
                  placeholder="you@example.com"
                  required
                />
              </div>

              <div>
                <label className="block text-xs mb-1 text-slate-300">
                  Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-700 text-sm outline-none focus:border-blue-500"
                  placeholder="••••••••"
                  required
                />
              </div>

              {error && (
                <p className="text-xs text-red-400">{error}</p>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full mt-2 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-sm font-medium text-white disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
              >
                {loading
                  ? "Please wait…"
                  : mode === "login"
                  ? "Login"
                  : "Sign Up"}
              </button>
            </form>

            <div className="mt-4 text-center">
              <button
                type="button"
                onClick={toggleMode}
                className="text-xs text-slate-400 hover:text-blue-400 transition-colors"
              >
                {mode === "login"
                  ? "Don't have an account? Sign up"
                  : "Already have an account? Login"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
