import { isApiError } from "@/lib/api/errors";

/** Show provider-supplied guidance without guessing a quota reset schedule. */
export function actionErrorMessage(error: Error): string {
  if (
    !isApiError(error) ||
    !["AI_DAILY_LIMIT_REACHED", "AI_SERVICE_BUSY"].includes(error.code)
  )
    return error.message;
  const retryAt = error.details?.retry_at;
  if (typeof retryAt !== "string") return error.message;
  const retryDate = new Date(retryAt);
  if (!Number.isFinite(retryDate.getTime())) return error.message;
  const formatted = new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  }).format(retryDate);
  return `${error.message} Suggested retry: ${formatted}.`;
}
