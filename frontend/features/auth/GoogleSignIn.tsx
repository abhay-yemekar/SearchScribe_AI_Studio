"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Script from "next/script";
import { z } from "zod";
import { apiFetch } from "@/lib/api/client";

const challengeSchema = z.discriminatedUnion("enabled", [
  z.object({ enabled: z.literal(false) }),
  z.object({ enabled: z.literal(true), client_id: z.string(), nonce: z.string() }),
]);

export type GoogleChallenge = z.infer<typeof challengeSchema>;

function loginChallenge() {
  return apiFetch<unknown>("/api/v1/auth/google/challenge", {}, { skipAuth: true });
}

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
  challengeLoader = loginChallenge,
  unavailableMessage = "Google sign-in is unavailable on this instance. Continue with email and password.",
  failureMessage = "Google sign-in is unavailable. Password login is still available.",
  verificationLabel = "Verifying Google sign-in…",
}: {
  onCredential: (credential: string) => Promise<void>;
  onError: (message: string) => void;
  showUnavailableMessage?: boolean;
  challengeLoader?: () => Promise<unknown>;
  unavailableMessage?: string;
  failureMessage?: string;
  verificationLabel?: string;
}) {
  const [challenge, setChallenge] = useState<z.infer<typeof challengeSchema> | null>(
    null,
  );
  const [sdkReady, setSdkReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [loadFailed, setLoadFailed] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const callback = useRef(onCredential);
  const errorCallback = useRef(onError);
  const active = useRef(false);
  const processing = useRef(false);
  const generation = useRef(0);
  useEffect(() => {
    callback.current = onCredential;
    errorCallback.current = onError;
  });

  useEffect(() => {
    let cancelled = false;
    active.current = true;
    generation.current++;
    // A fresh provider challenge replaces the old SDK authorization boundary.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setChallenge(null);
    void challengeLoader()
      .then((data) => {
        if (!cancelled) {
          setChallenge(challengeSchema.parse(data));
          setLoadFailed(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoadFailed(true);
          setChallenge(null);
          errorCallback.current(failureMessage);
        }
      });
    return () => {
      cancelled = true;
      active.current = false;
    };
  }, [attempt, challengeLoader, failureMessage]);

  const render = useCallback(() => {
    const sdk = (window as Window & { google?: GoogleSdk }).google;
    if (!sdk || !container.current || !challenge?.enabled) return;
    const currentGeneration = generation.current;
    sdk.accounts.id.initialize({
      client_id: challenge.client_id,
      nonce: challenge.nonce,
      auto_select: false,
      callback: ({ credential }) => {
        if (
          !active.current ||
          generation.current !== currentGeneration ||
          processing.current
        )
          return;
        processing.current = true;
        setBusy(true);
        void callback
          .current(credential)
          .catch((error: unknown) => {
            if (active.current && generation.current === currentGeneration)
              errorCallback.current(
                error instanceof Error ? error.message : "Google sign-in failed.",
              );
          })
          .finally(() => {
            processing.current = false;
            if (active.current && generation.current === currentGeneration) {
              setBusy(false);
              setChallenge(null);
              setAttempt((value) => value + 1);
            }
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
  if (loadFailed)
    return (
      <button
        type="button"
        onClick={() => {
          setLoadFailed(false);
          setAttempt((value) => value + 1);
        }}
        className="my-4 block text-sm font-medium underline underline-offset-4"
      >
        Retry Google connection
      </button>
    );
  if (!challenge?.enabled) {
    return challenge?.enabled === false && showUnavailableMessage ? (
      <p
        role="status"
        className="my-4 text-center text-xs leading-relaxed text-slate-600"
      >
        {unavailableMessage}
      </p>
    ) : null;
  }
  return (
    <div className="my-4 flex flex-col items-center gap-2">
      <Script
        src="https://accounts.google.com/gsi/client"
        strategy="afterInteractive"
        onReady={() => {
          if (active.current) setSdkReady(true);
        }}
        onError={() => {
          if (active.current) onError(failureMessage);
        }}
      />
      <div ref={container} className={busy ? "pointer-events-none opacity-60" : ""} />
      {busy && (
        <p role="status" className="text-sm text-slate-600">
          {verificationLabel}
        </p>
      )}
    </div>
  );
}
