"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import BrandLogo from "@/components/brand/BrandLogo";
import { ArticleSkeleton, Spinner } from "@/components/shared/States";

export default function SessionLoading() {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), 8000);
    return () => clearTimeout(timer);
  }, []);
  return (
    <main className="studio-shell min-h-screen px-6 py-8 sm:px-12">
      <header className="mx-auto flex max-w-6xl items-center justify-between gap-6 border-b border-stone-300 pb-6">
        <Link href="/" aria-label="SearchScribe home">
          <BrandLogo />
        </Link>
        <Link href="/" className="text-sm underline underline-offset-4">
          Website
        </Link>
      </header>
      <div className="mx-auto max-w-4xl py-12">
        <p className="text-xs uppercase tracking-widest text-slate-500">
          Your writing desk
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight">
          Opening your workspace
        </h1>
        <p role="status" className="my-6 flex items-center gap-3 text-sm text-slate-600">
          <Spinner />{" "}
          {slow
            ? "Your workspace is taking a little longer to open. You can keep browsing the website."
            : "Restoring session…"}
        </p>
        <div
          aria-hidden="true"
          className="studio-panel rounded-xl border border-stone-200 bg-white p-6"
        >
          <ArticleSkeleton />
        </div>
      </div>
    </main>
  );
}
