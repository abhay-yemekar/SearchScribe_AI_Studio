import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import BrandLogo from "@/components/brand/BrandLogo";

export const recoveryInputClass =
  "w-full rounded border border-stone-300 bg-white px-3 py-3 text-sm text-[#17252b] outline-none focus:border-[#17252b] focus-visible:ring-2 focus-visible:ring-[#17252b]/20";
export const recoveryButtonClass =
  "studio-primary-action inline-flex w-full items-center justify-center gap-2 bg-[#17252b] px-4 py-3 text-sm font-semibold text-white hover:bg-[#293f48] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#17252b] disabled:cursor-not-allowed disabled:opacity-60";
export const recoveryLinkClass =
  "font-medium underline underline-offset-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#17252b]";

export default function RecoveryShell({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <main className="login-shell min-h-screen bg-[#f4f5f1] px-5 py-8 text-[#17252b] sm:px-8 sm:py-10">
      <div className="mx-auto w-full max-w-6xl">
        <header className="login-header flex flex-col items-start gap-5 border-b border-stone-300 pb-6 sm:flex-row sm:items-center sm:justify-between">
          <Link
            href="/login"
            className={`inline-flex items-center gap-2 text-sm ${recoveryLinkClass}`}
          >
            <ArrowLeft aria-hidden className="h-4 w-4" /> Back to login
          </Link>
          <Link href="/" aria-label="SearchScribe home">
            <BrandLogo />
          </Link>
        </header>
        <section
          aria-labelledby="recovery-title"
          className="login-panel mx-auto my-10 w-full max-w-md border border-stone-300 bg-white p-6 sm:my-14 sm:p-8"
        >
          <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Your SearchScribe account
          </p>
          <h1 id="recovery-title" className="text-3xl font-semibold tracking-tight">
            {title}
          </h1>
          <p className="mb-6 mt-3 text-sm leading-relaxed text-slate-600">
            {description}
          </p>
          {children}
        </section>
      </div>
    </main>
  );
}
