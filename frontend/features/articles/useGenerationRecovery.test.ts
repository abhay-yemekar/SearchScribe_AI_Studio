import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/errors";
import { useGenerationRecovery } from "./useGenerationRecovery";

const api = vi.hoisted(() => ({ apiFetch: vi.fn() }));
vi.mock("@/lib/api/client", () => api);

beforeEach(() => {
  sessionStorage.clear();
  api.apiFetch.mockReset();
});
afterEach(cleanup);

describe("generation recovery", () => {
  it("retains a lost-response request across remount and recovers its saved article", async () => {
    const action = vi.fn().mockRejectedValue(new TypeError("Network response lost"));
    const first = renderHook(() => useGenerationRecovery(17));
    await act(async () => {
      await expect(first.result.current.run(action)).rejects.toThrow("Network response lost");
    });
    const key = first.result.current.pendingKey;
    expect(key).toMatch(/^[\w-]{36}$/);
    first.unmount();
    const restored = renderHook(() => useGenerationRecovery(17));
    expect(restored.result.current.pendingKey).toBe(key);
    api.apiFetch.mockResolvedValue({ status: "completed", article_id: 42 });
    await act(async () => { expect(await restored.result.current.check()).toBe(42); });
    expect(action).toHaveBeenCalledTimes(1);
    expect(api.apiFetch).toHaveBeenCalledWith(`/api/v1/generation-requests/${key}`);
    expect(restored.result.current.pendingKey).toBeNull();
    expect(sessionStorage.length).toBe(0);
  });

  it("blocks new AI work until an ambiguous request has resolved", async () => {
    const hook = renderHook(() => useGenerationRecovery(17));
    await act(async () => {
      await expect(hook.result.current.run(() => Promise.reject(new Error("lost"))))
        .rejects.toThrow();
    });
    const another = vi.fn();
    await expect(hook.result.current.run(another)).rejects.toThrow("previous generation");
    expect(another).not.toHaveBeenCalled();
    api.apiFetch.mockResolvedValue({ status: "processing", article_id: null });
    await act(async () => { await hook.result.current.check(); });
    expect(hook.result.current.pendingKey).not.toBeNull();
    expect(hook.result.current.notice).toContain("still running");
  });

  it("permits a new attempt after a definite quota rejection without keeping content", async () => {
    const hook = renderHook(() => useGenerationRecovery(17));
    const error = new ApiError(429, { error: {
      code: "GENERATION_DAILY_LIMIT", message: "Daily limit reached", request_id: "test",
    } });
    await act(async () => {
      await expect(hook.result.current.run(() => Promise.reject(error))).rejects.toThrow();
    });
    expect(hook.result.current.pendingKey).toBeNull();
    expect(sessionStorage.length).toBe(0);
  });

  it("does not hold back the next attempt after an unverified-email rejection", async () => {
    const hook = renderHook(() => useGenerationRecovery(17));
    const error = new ApiError(403, { error: {
      code: "EMAIL_VERIFICATION_REQUIRED", message: "Verify your email", request_id: "test",
    } });
    await act(async () => {
      await expect(hook.result.current.run(() => Promise.reject(error))).rejects.toThrow();
    });
    expect(hook.result.current.pendingKey).toBeNull();
    const next = vi.fn().mockResolvedValue(7);
    await act(async () => { expect(await hook.result.current.run(next)).toBe(7); });
    expect(next).toHaveBeenCalledTimes(1);
  });

  it("keeps failed status lookups retryable and isolates users", async () => {
    const first = renderHook(() => useGenerationRecovery(17));
    await act(async () => {
      await expect(first.result.current.run(() => Promise.reject(new Error("lost"))))
        .rejects.toThrow();
    });
    const other = renderHook(() => useGenerationRecovery(18));
    expect(other.result.current.pendingKey).toBeNull();
    api.apiFetch.mockRejectedValue(new TypeError("Offline"));
    await act(async () => { await first.result.current.check(); });
    expect(first.result.current.pendingKey).not.toBeNull();
    expect(first.result.current.notice).toContain("kept");
    api.apiFetch.mockResolvedValue({ status: "interrupted", article_id: null });
    await act(async () => { await first.result.current.check(); });
    expect(first.result.current.pendingKey).toBeNull();
    expect(first.result.current.notice).toContain("did not complete");
  });
});
