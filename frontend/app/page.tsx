import Link from "next/link";
import Image from "next/image";
import { ArrowRight, ArrowUpRight, FileText, History, PenLine } from "lucide-react";
import SiteChrome from "@/components/marketing/SiteChrome";

const capabilities = [
  {
    icon: FileText,
    title: "A draft with structure",
    detail: "Turn a topic into a sectioned article you can refine.",
  },
  {
    icon: PenLine,
    title: "An editor's final say",
    detail: "Edit the article and its SEO title, description, and keywords.",
  },
  {
    icon: History,
    title: "Room to revise",
    detail: "Try a rewrite, compare versions, and restore an earlier one.",
  },
];

export default function HomePage() {
  return (
    <SiteChrome>
      <section className="overflow-hidden border-b border-stone-200">
        <div className="mx-auto grid max-w-7xl gap-12 px-5 pb-20 pt-16 sm:px-8 md:pb-28 md:pt-24 lg:grid-cols-[1.12fr_.88fr] lg:items-end lg:gap-20 lg:px-12">
          <div>
            <p className="mb-6 flex items-center gap-3 text-xs font-semibold uppercase tracking-[.2em] text-teal-800">
              <span className="h-px w-8 bg-teal-700" /> The open-source writing studio
            </p>
            <h1 className="max-w-3xl font-serif text-[clamp(3.7rem,7vw,7.1rem)] leading-[.97] tracking-[-.06em] text-slate-900">
              Start with a thought.{" "}
              <em className="font-normal text-teal-800">Leave with a draft.</em>
            </h1>
            <p className="mt-8 max-w-xl text-lg leading-8 text-slate-600">
              SearchScribe helps you shape a topic into an article, tune the SEO details,
              revise with intent, and export clean HTML. You stay the editor.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-5">
              <Link
                href="/login?mode=signup"
                className="inline-flex min-h-12 items-center gap-3 rounded-full bg-teal-800 px-6 py-3 font-semibold text-white hover:bg-teal-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-800"
              >
                Start writing <ArrowUpRight aria-hidden className="h-5 w-5" />
              </Link>
              <Link
                href="/how-it-works"
                className="inline-flex items-center gap-2 border-b border-slate-500 py-2 font-semibold text-slate-800 hover:text-teal-800"
              >
                See how it works <ArrowRight aria-hidden className="h-4 w-4" />
              </Link>
            </div>
            <p className="mt-5 text-xs text-slate-500">
              Free, noncommercial beta · Password sign-in available · Google sign-in in
              development
            </p>
          </div>
          <div className="border border-stone-300 bg-[#e5e8e2] p-4 shadow-[20px_20px_0_#d9ddd4] sm:p-7">
            <div className="flex items-center justify-between border-b border-teal-900/20 pb-4 text-xs font-semibold uppercase tracking-[.16em] text-teal-900">
              <span>Inside the studio</span>
              <span>01 / 03</span>
            </div>
            <div className="mt-10 rounded-xl border border-stone-200 bg-[#faf9f5] p-5 shadow-sm sm:p-7">
              <p className="text-xs font-semibold uppercase tracking-[.18em] text-teal-800">
                Topic / search query
              </p>
              <p className="mt-2 border-b border-stone-300 pb-3 text-sm text-slate-700">
                Things to do in Kerala
              </p>
              <p className="mt-7 text-xs font-semibold uppercase tracking-[.18em] text-teal-800">
                Article draft
              </p>
              <h2 className="mt-3 font-serif text-3xl leading-tight text-slate-900 sm:text-4xl">
                A first look at Kerala
              </h2>
              <p className="mt-4 text-sm leading-7 text-slate-600">
                From the quiet backwaters to the hills of Munnar, organize the places you
                want to explore into a draft you can make your own.
              </p>
              <div className="mt-7 flex gap-2 border-t border-stone-200 pt-4 text-xs text-slate-500">
                <span className="rounded-full bg-stone-100 px-3 py-1">Article</span>
                <span className="px-3 py-1">SEO</span>
                <span className="px-3 py-1">Versions</span>
              </div>
            </div>
            <p className="mt-5 text-xs leading-5 text-slate-600">
              Illustrative interface preview. Example text is editorial sample copy, not
              researched travel advice.
            </p>
          </div>
        </div>
      </section>
      <section className="mx-auto max-w-7xl px-5 py-20 sm:px-8 lg:px-12">
        <div className="grid gap-6 md:grid-cols-[.75fr_1.25fr] md:gap-16">
          <p className="text-xs font-semibold uppercase tracking-[.2em] text-teal-800">
            Made for the messy middle
          </p>
          <h2 className="font-serif text-4xl leading-tight tracking-tight sm:text-5xl">
            A useful first draft is just the beginning. The work is in what you do next.
          </h2>
        </div>
        <div className="mt-12 grid gap-5 md:grid-cols-3">
          {capabilities.map(({ icon: Icon, title, detail }, index) => (
            <article key={title} className="border-t border-stone-300 pt-6">
              <div className="flex items-center justify-between text-teal-800">
                <Icon aria-hidden className="h-6 w-6" />
                <span className="text-xs">0{index + 1}</span>
              </div>
              <h3 className="mt-8 font-serif text-2xl">{title}</h3>
              <p className="mt-3 text-sm leading-7 text-slate-600">{detail}</p>
            </article>
          ))}
        </div>
      </section>
      <section className="border-t border-stone-200 bg-[#e7e9e2] px-5 py-20 sm:px-8 lg:px-12">
        <div className="mx-auto max-w-7xl">
          <div className="mb-8 grid gap-4 md:grid-cols-[1fr_1fr] md:items-end">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[.2em] text-teal-800">
                A look inside
              </p>
              <h2 className="mt-4 font-serif text-4xl tracking-tight sm:text-5xl">
                The workspace, as it is today.
              </h2>
            </div>
            <p className="max-w-lg leading-7 text-slate-600">
              This screenshot was captured from the working local interface using its
              deterministic mock AI provider. It shows the article editor; live AI
              output varies with your topic.
            </p>
          </div>
          <Image
            src="/studio-preview.png"
            alt="SearchScribe article workspace showing a mock-generated Kerala draft, editing tabs, version controls, and export action"
            width={1440}
            height={900}
            className="w-full rounded-xl border border-stone-300 shadow-xl"
            sizes="(max-width: 1280px) 100vw, 1280px"
          />
        </div>
      </section>
      <section className="bg-teal-900 px-5 py-20 text-white sm:px-8 lg:px-12">
        <div className="mx-auto grid max-w-7xl gap-8 md:grid-cols-[1fr_auto] md:items-end">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[.2em] text-teal-200">
              What comes next
            </p>
            <h2 className="mt-5 max-w-3xl font-serif text-4xl leading-tight sm:text-5xl">
              Research you can trace. Photos you can credit.
            </h2>
            <p className="mt-5 max-w-2xl leading-7 text-teal-100">
              Source-backed research, relevant licensed photos, and Google sign-in are on
              the public beta roadmap. They are not available in the current workspace.
            </p>
          </div>
          <Link
            href="/features"
            className="inline-flex items-center gap-2 border-b border-teal-200 pb-2 font-semibold hover:text-teal-200"
          >
            Explore features <ArrowUpRight aria-hidden className="h-4 w-4" />
          </Link>
        </div>
      </section>
      <section className="mx-auto grid max-w-7xl gap-8 px-5 py-20 sm:px-8 md:grid-cols-[1fr_auto] md:items-center lg:px-12">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[.2em] text-teal-800">
            Ready for a blank page?
          </p>
          <h2 className="mt-4 font-serif text-4xl tracking-tight sm:text-5xl">
            Make something worth revising.
          </h2>
        </div>
        <Link
          href="/login?mode=signup"
          className="inline-flex items-center gap-2 rounded-full bg-teal-800 px-6 py-3 font-semibold text-white hover:bg-teal-900"
        >
          Start writing <ArrowUpRight aria-hidden className="h-4 w-4" />
        </Link>
      </section>
    </SiteChrome>
  );
}
