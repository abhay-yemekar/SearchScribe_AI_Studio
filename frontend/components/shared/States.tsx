"use client";

/** Reusable loading / empty / error UI primitives. */

export function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <span
      aria-label="Loading"
      className={`inline-block animate-spin rounded-full border-2 border-current border-t-transparent ${className}`}
    />
  );
}

export function SkeletonBlock({ className = "h-4 w-full" }: { className?: string }) {
  return (
    <div aria-hidden className={`animate-pulse rounded bg-stone-200 ${className}`} />
  );
}

export function ArticleSkeleton() {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Loading article">
      <SkeletonBlock className="h-7 w-2/3" />
      <SkeletonBlock className="h-4 w-1/2" />
      <SkeletonBlock className="h-4 w-full" />
      <SkeletonBlock className="h-4 w-full" />
      <SkeletonBlock className="h-4 w-5/6" />
      <SkeletonBlock className="h-5 w-1/3" />
      <SkeletonBlock className="h-4 w-full" />
      <SkeletonBlock className="h-4 w-4/6" />
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 py-16 text-center">
      <p className="text-sm font-medium text-slate-700">{title}</p>
      {hint ? <p className="max-w-sm text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <p
      role="alert"
      className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800"
    >
      {message}
    </p>
  );
}

export function SuccessBanner({ message }: { message: string }) {
  return (
    <p
      role="status"
      className="rounded-lg border border-teal-200 bg-teal-50 px-3 py-2 text-sm text-teal-800"
    >
      {message}
    </p>
  );
}
