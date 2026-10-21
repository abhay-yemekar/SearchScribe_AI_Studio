// Security headers for HTML pages. Plain JS so next.config.mjs and proxy.ts share it.
// API responses carry the backend's own headers (backend/app/core/middleware.py).

const GOOGLE_SIGN_IN = "https://accounts.google.com/gsi/";
const COMMONS_IMAGES = ["https://upload.wikimedia.org", "https://thumb.wikimedia.org"];

// Pages that handle accounts, sessions or drafts. proxy.ts gives these a per-request
// nonce CSP (so they render dynamically); public pages stay static with a fixed CSP.
export const APP_PATHS = [
  "/dashboard",
  "/account",
  "/login",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
];

/** @param {string} pathname */
export function isAppPath(pathname) {
  return APP_PATHS.some((path) => pathname === path || pathname.startsWith(`${path}/`));
}

/**
 * With a nonce, only scripts Next.js signs for this request (and scripts they load,
 * via 'strict-dynamic') run. Without one, inline scripts are allowed so public pages
 * can stay static; framing, plugins and unknown origins are blocked either way.
 * Styles allow inline: the sandboxed HTML preview and Google's button use them.
 *
 * @param {{ nonce?: string, dev?: boolean }} options
 */
export function contentSecurityPolicy({ nonce, dev = false } = {}) {
  const scripts = nonce
    ? ["'self'", `'nonce-${nonce}'`, "'strict-dynamic'"]
    : ["'self'", "'unsafe-inline'", `${GOOGLE_SIGN_IN}client`];
  // React's dev build uses eval for error stacks; the dev server reloads over a websocket.
  if (dev) scripts.push("'unsafe-eval'");
  return [
    "default-src 'self'",
    `script-src ${scripts.join(" ")}`,
    `style-src 'self' 'unsafe-inline' ${GOOGLE_SIGN_IN}style`,
    `img-src 'self' data: blob: ${COMMONS_IMAGES.join(" ")}`,
    "font-src 'self'",
    `connect-src 'self' ${GOOGLE_SIGN_IN}${dev ? " ws: wss:" : ""}`,
    `frame-src ${GOOGLE_SIGN_IN}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}

export const BASE_HEADERS = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Older browsers ignore CSP frame-ancestors; this keeps clickjacking out there too.
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const appPattern = APP_PATHS.map((path) => path.slice(1)).join("|");
// Everything except /api, Next's own files and the app pages (path-to-regexp syntax).
export const PUBLIC_PAGES_SOURCE = `/:path((?!(?:api|_next|${appPattern})(?:/|$)).*)`;
export const NON_API_SOURCE = "/:path((?!api(?:/|$)).*)";
