import * as Sentry from "@sentry/browser";

/** Drop the query and fragment: reset and verification links carry tokens there. */
export function withoutQuery(url: string): string {
  return url.split(/[?#]/, 1)[0];
}

// The SDK records page URLs on events and navigation breadcrumbs as they are,
// so a crash after opening a reset link would otherwise send its token.
function scrubBreadcrumb(breadcrumb: Sentry.Breadcrumb): Sentry.Breadcrumb {
  const data = breadcrumb.data;
  for (const key of ["from", "to", "url"]) {
    if (typeof data?.[key] === "string") data[key] = withoutQuery(data[key]);
  }
  return breadcrumb;
}

function scrubEvent<T extends Sentry.Event>(event: T): T {
  if (event.request) {
    if (event.request.url) event.request.url = withoutQuery(event.request.url);
    delete event.request.query_string;
  }
  return event;
}

/**
 * Browser error tracking. With no NEXT_PUBLIC_SENTRY_DSN this does nothing.
 * The DSN is public by design; it only lets the browser send error reports.
 */
export function initSentry(dsn = process.env.NEXT_PUBLIC_SENTRY_DSN): boolean {
  if (!dsn || typeof window === "undefined") return false;
  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_VERCEL_ENV ?? process.env.NODE_ENV,
    release: process.env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA || undefined,
    // Errors only: no performance tracing, no session replay, no personal data.
    tracesSampleRate: 0,
    dataCollection: {
      userInfo: false,
      cookies: false,
      httpHeaders: false,
      httpBodies: [],
      urlQueryParams: false,
    },
    beforeBreadcrumb: scrubBreadcrumb,
    beforeSend: scrubEvent,
  });
  return true;
}

/** Report a caught error. Without initSentry this is dropped by the SDK. */
export function reportError(error: unknown): void {
  Sentry.captureException(error);
}
