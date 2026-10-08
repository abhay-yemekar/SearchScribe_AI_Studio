"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Script from "next/script";
import { z } from "zod";
import { apiFetch } from "@/lib/api/client";

const challengeSchema = z.discriminatedUnion("enabled", [
  z.object({ enabled: z.literal(false) }),
  z.object({ enabled: z.literal(true), client_id: z.string(), nonce: z.string() }),
]);

type GoogleSdk = {
  accounts: {
    id: {
      initialize: (input: {
        client_id: string;
        nonce: string;
        auto_select: boolean;
        callback: (response: { credential: string }) => void;
      }) => void;
      renderButton: (
        container: HTMLElement,
        options: Record<string, string | number>,
      ) => void;
    };
  };
};

export default function GoogleSignIn({
  onCredential,
  onError,
  showUnavailableMessage = false,
}: {
  onCredential: (credential: string) => Promise<void>;
  onError: (message: string) => void;
  showUnavailableMessage?: boolean;
}) {
  const [challenge, setChallenge] = useState<z.infer<typeof challengeSchema> | null>(
    null,
  );
  const [sdkReady, setSdkReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const container = useRef<HTMLDivElement>(null);
  const callback = useRef(onCredential);
  const errorCallback = useRef(onError);
  useEffect(() => {
    callback.current = onCredential;
    errorCallback.current = onError;
  });

  useEffect(() => {
    let cancelled = false;
    void apiFetch<unknown>("/api/v1/auth/google/challenge", {}, { skipAuth: true })
      .then((data) => {
        if (!cancelled) setChallenge(challengeSchema.parse(data));
      })
      .catch(() => {
        if (!cancelled)
          errorCallback.current(
            "Google sign-in is unavailable. Password login is still available.",
          );
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const render = useCallback(() => {
    const sdk = (window as Window & { google?: GoogleSdk }).google;
    if (!sdk || !container.current || !challenge?.enabled) return;
    sdk.accounts.id.initialize({
      client_id: challenge.client_id,
      nonce: challenge.nonce,
      auto_select: false,
      callback: ({ credential }) => {
        setBusy(true);
        void callback
          .current(credential)
          .catch((error: unknown) => {
            errorCallback.current(
              error instanceof Error ? error.message : "Google sign-in failed.",
            );
          })
          .finally(() => {
            setBusy(false);
            setAttempt((value) => value + 1);
          });
      },
    });
    container.current.replaceChildren();
    sdk.accounts.id.renderButton(container.current, {
      type: "standard",
      theme: "outline",
      size: "large",
      text: "signin_with",
      width: 280,
    });
  }, [challenge]);

  useEffect(() => {
    if (sdkReady) render();
  }, [sdkReady, render]);
  if (!challenge?.enabled) {
    return challenge?.enabled === false && showUnavailableMessage ? (
      <p
        role="status"
        className="my-4 text-center text-xs leading-relaxed text-slate-600"
      >
        Google sign-in is unavailable on this instance. Continue with email and password.
      </p>
    ) : null;
  }
  return (
    <div className="my-4 flex flex-col items-center gap-2">
      <Script
        src="https://accounts.google.com/gsi/client"
        strategy="afterInteractive"
        onReady={() => setSdkReady(true)}
        onError={() =>
          onError("Google sign-in could not load. Please use password login.")
        }
      />
      <div ref={container} className={busy ? "pointer-events-none opacity-60" : ""} />
      {busy && (
        <p role="status" className="text-sm text-slate-600">
          Verifying Google sign-in…
        </p>
      )}
    </div>
  );
}
