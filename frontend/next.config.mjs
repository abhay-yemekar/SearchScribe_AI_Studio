/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // Same-origin proxy to the backend: the browser only ever talks to
    // localhost:3000, which keeps the refresh cookie first-party (SameSite=Lax)
    // and avoids CORS entirely in development.
    const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
