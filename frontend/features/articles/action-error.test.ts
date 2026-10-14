import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api/errors";
import { actionErrorMessage } from "./action-error";

function limit(details?: Record<string, unknown>, code = "AI_DAILY_LIMIT_REACHED") {
  return new ApiError(503, {
    error: { code, message: "Daily limit reached.", request_id: "fixture", details },
  });
}

describe("AI service limit guidance", () => {
  it("shows a dated retry suggestion in the browser's local timezone", () => {
    const date = new Date("2026-10-15T00:00:00Z");
    const formatted = new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short",
    }).format(date);
    expect(actionErrorMessage(limit({ retry_at: date.toISOString() }))).toBe(
      `Daily limit reached. Suggested retry: ${formatted}.`,
    );
  });
  it.each([undefined, {}, { retry_at: "not-a-date" }, { retry_at: 20 }])(
    "does not invent a reset time without valid guidance (%s)",
    (details) => {
      expect(actionErrorMessage(limit(details))).toBe("Daily limit reached.");
    },
  );
  it("keeps other action errors unchanged", () => {
    expect(actionErrorMessage(new Error("Network unavailable"))).toBe(
      "Network unavailable",
    );
    expect(
      actionErrorMessage(limit({ retry_at: "2026-10-15T00:00:00Z" }, "VERSION_CONFLICT")),
    ).toBe("Daily limit reached.");
  });
});
