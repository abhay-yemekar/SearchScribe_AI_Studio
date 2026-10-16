// Read by backend/app/core/rate_limit.py; the API trusts the IP only with the secret.
export const CLIENT_IP_HEADER = "x-client-ip";
export const PROXY_SECRET_HEADER = "x-proxy-secret";

type ProxyEnv = { secret?: string; onVercel: boolean };

/**
 * Request headers for an `/api` call forwarded to the backend.
 *
 * Behind Vercel and Render the API only sees a proxy address shared by every
 * visitor, so rate limits need the real client IP passed along. Vercel
 * overwrites `x-real-ip` with the connecting client's address, so it is only
 * read there. Whatever a browser sent under either forwarded name is dropped.
 */
export function apiRequestHeaders(incoming: Headers, env: ProxyEnv): Headers {
  const headers = new Headers(incoming);
  headers.delete(CLIENT_IP_HEADER);
  headers.delete(PROXY_SECRET_HEADER);
  const ip = env.onVercel ? incoming.get("x-real-ip")?.trim() : undefined;
  if (env.secret && ip) {
    headers.set(CLIENT_IP_HEADER, ip);
    headers.set(PROXY_SECRET_HEADER, env.secret);
  }
  return headers;
}
