import Link from "next/link";
import { ArrowUpRight, Feather, Menu } from "lucide-react";

const links = [
  { href: "/how-it-works", label: "How it works" },
  { href: "/features", label: "Features" },
  { href: "/example", label: "Example" },
];

export default function SiteChrome({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[#f5f3ee] text-slate-900">
      <header className="relative z-10 border-b border-stone-200/90 bg-[#f5f3ee]/95">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-5 py-4 sm:px-8 lg:px-12">
          <Link
            href="/"
            className="flex items-center gap-2.5 font-serif text-xl font-bold tracking-tight focus-visible:outline-teal-700"
          >
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-teal-800 text-white">
              <Feather aria-hidden className="h-4 w-4" />
            </span>
            SearchScribe<span className="sr-only"> home</span>
          </Link>
          <nav
            aria-label="Main navigation"
            className="hidden items-center gap-8 text-sm font-medium text-slate-700 md:flex"
          >
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="hover:text-teal-800 focus-visible:outline-teal-700"
              >
                {link.label}
              </Link>
            ))}
          </nav>
          <div className="hidden items-center gap-3 md:flex">
            <Link
              href="/login"
              className="px-3 py-2 text-sm font-semibold text-slate-700 hover:text-teal-800"
            >
              Log in
            </Link>
            <Link
              href="/login?mode=signup"
              className="inline-flex items-center gap-2 rounded-full bg-teal-800 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-900"
            >
              Start writing <ArrowUpRight aria-hidden className="h-4 w-4" />
            </Link>
          </div>
          <details className="relative md:hidden">
            <summary
              aria-label="Open navigation"
              className="flex cursor-pointer list-none items-center justify-center rounded-lg border border-stone-300 p-2 marker:hidden"
            >
              <Menu aria-hidden className="h-5 w-5" />
            </summary>
            <nav
              aria-label="Mobile navigation"
              className="absolute right-0 top-12 flex w-56 flex-col gap-1 rounded-xl border border-stone-200 bg-white p-2 text-sm shadow-xl"
            >
              {links.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="rounded-lg px-3 py-2 hover:bg-stone-100"
                >
                  {link.label}
                </Link>
              ))}
              <Link href="/login" className="rounded-lg px-3 py-2 hover:bg-stone-100">
                Log in
              </Link>
              <Link
                href="/login?mode=signup"
                className="rounded-lg bg-teal-800 px-3 py-2 font-semibold text-white"
              >
                Start writing
              </Link>
            </nav>
          </details>
        </div>
      </header>
      <main id="main-content">{children}</main>
      <footer className="border-t border-stone-200 bg-[#eceae3]">
        <div className="mx-auto grid max-w-7xl gap-8 px-5 py-12 sm:px-8 md:grid-cols-[1fr_auto] lg:px-12">
          <div>
            <p className="font-serif text-xl font-semibold">SearchScribe</p>
            <p className="mt-2 max-w-md text-sm leading-6 text-slate-600">
              A writing workspace built for editorial control. Public beta features are
              being completed in the open.
            </p>
          </div>
          <div className="flex flex-wrap content-start gap-x-6 gap-y-3 text-sm text-slate-600">
            <Link href="/how-it-works" className="hover:text-teal-800">
              How it works
            </Link>
            <Link href="/features" className="hover:text-teal-800">
              Features
            </Link>
            <Link href="/example" className="hover:text-teal-800">
              Example
            </Link>
            <Link href="/privacy" className="hover:text-teal-800">
              Privacy
            </Link>
            <a
              href="https://github.com/abhay-yemekar/SearchScribe_AI_Studio"
              target="_blank"
              rel="noreferrer"
              className="hover:text-teal-800"
            >
              Open-source code ↗
            </a>
          </div>
          <p className="text-xs text-slate-500 md:col-span-2">
            Free, noncommercial beta. AI drafts need human review before publication.
            Research citations and licensed photo suggestions are in development.
          </p>
        </div>
      </footer>
    </div>
  );
}
