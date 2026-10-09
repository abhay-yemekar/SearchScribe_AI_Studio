import { isApiError } from "@/lib/api/errors";

export function recoveryError(error: unknown): string {
  if (isApiError(error)) {
    if (error.status === 429)
      return "Too many requests. Wait a few minutes and try again.";
    if (error.status === 503)
      return "Email delivery is unavailable on this instance. Try again later. If you use Google sign-in, continue with Google.";
  }
  return "Could not complete this request. Check your connection and try again.";
}
