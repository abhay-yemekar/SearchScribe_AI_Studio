import { NextResponse, type NextRequest } from "next/server";

import { apiRequestHeaders } from "@/lib/api/client-ip";

// Runs before the next.config.mjs `/api` rewrite; the headers set here reach the API.
export function proxy(request: NextRequest) {
  const headers = apiRequestHeaders(request.headers, {
    secret: process.env.PROXY_SHARED_SECRET,
    onVercel: process.env.VERCEL === "1",
  });
  return NextResponse.next({ request: { headers } });
}

export const config = { matcher: "/api/:path*" };
