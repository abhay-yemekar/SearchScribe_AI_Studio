"use client";

import { useEffect } from "react";

import { reportError } from "@/lib/sentry";

// Replaces the root layout when it crashes, so it brings its own document and styles.
export default function GlobalError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  useEffect(() => {
    reportError(error);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
          background: "#f4f5f1",
          color: "#17252b",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <title>Something went wrong | SearchScribe</title>
        <main style={{ maxWidth: 420, padding: 24, textAlign: "center" }}>
          <h1 style={{ fontSize: 28, margin: "0 0 12px" }}>Something went wrong</h1>
          <p style={{ lineHeight: 1.6, margin: "0 0 24px" }}>
            This page hit an unexpected error. Saved versions of your articles are kept.
          </p>
          <button
            type="button"
            onClick={() => retry()}
            style={{
              background: "#17252b",
              color: "#fff",
              border: 0,
              borderRadius: 8,
              padding: "10px 18px",
              fontSize: 15,
              cursor: "pointer",
            }}
          >
            Try again
          </button>
          <p style={{ marginTop: 16 }}>
            {/* A full page load, not client routing: the app shell itself crashed. */}
            {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
            <a href="/" style={{ color: "#17252b" }}>
              Go to the homepage
            </a>
          </p>
        </main>
      </body>
    </html>
  );
}
