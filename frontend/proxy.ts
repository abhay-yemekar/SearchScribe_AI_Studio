import { NextResponse, type NextRequest } from "next/server";

import { apiRequestHeaders } from "@/lib/api/client-ip";
import { contentSecurityPolicy } from "@/lib/security-headers.mjs";

// /api: runs before the next.config.mjs rewrite; the headers set here reach the API.
// App pages: a fresh nonce per request. Next reads the CSP request header and signs its
// scripts with that nonce, which is why those pages render dynamically.
export function proxy(request: NextRequest) {
  if (request.nextUrl.pathname.startsWith("/api/")) {
    const headers = apiRequestHeaders(request.headers, {
      secret: process.env.PROXY_SHARED_SECRET,
      onVercel: process.env.VERCEL === "1",
    });
    return NextResponse.next({ request: { headers } });
  }

  const nonce = btoa(crypto.randomUUID());
  const csp = contentSecurityPolicy({
    nonce,
    dev: process.env.NODE_ENV === "development",
  });
  const headers = new Headers(request.headers);
  headers.set("x-nonce", nonce);
  headers.set("content-security-policy", csp);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set("content-security-policy", csp);
  return response;
}

// Keep in step with APP_PATHS in lib/security-headers.mjs (matchers must be literals).
export const config = {
  matcher: [
    "/api/:path*",
    "/dashboard/:path*",
    "/account/:path*",
    "/login/:path*",
    "/forgot-password/:path*",
    "/reset-password/:path*",
    "/verify-email/:path*",
  ],
};
