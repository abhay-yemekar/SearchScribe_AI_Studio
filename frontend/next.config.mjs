import {
  BASE_HEADERS,
  NON_API_SOURCE,
  PUBLIC_PAGES_SOURCE,
  contentSecurityPolicy,
} from "./lib/security-headers.mjs";

/** @type {import('next').NextConfig} */
const nextConfig = {
  agentRules: false,
  images: { qualities: [75, 85] },
  // Vercel uses its own build adapter; standalone output is for the Docker image.
  output: process.env.VERCEL ? undefined : "standalone",
  // Playwright opens 127.0.0.1 while Next's dev server starts on localhost.
  allowedDevOrigins: ["127.0.0.1"],
  async headers() {
    // Later entries win for the same header, so the recovery pages keep no-referrer.
    return [
      { source: NON_API_SOURCE, headers: BASE_HEADERS },
      {
        source: PUBLIC_PAGES_SOURCE,
        headers: [
          {
            key: "Content-Security-Policy",
            value: contentSecurityPolicy({ dev: process.env.NODE_ENV === "development" }),
          },
        ],
      },
      ...["/forgot-password", "/reset-password", "/verify-email"].map((source) => ({
        source,
        headers: [
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "Cache-Control", value: "no-store" },
        ],
      })),
    ];
  },
  async rewrites() {
    // Same-origin proxy to the backend: the browser only ever talks to
    // localhost:3000, which keeps the refresh cookie first-party (SameSite=Lax)
    // and avoids CORS entirely in development.
    const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
