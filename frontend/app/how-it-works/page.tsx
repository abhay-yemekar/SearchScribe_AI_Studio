import type { Metadata } from "next";
import SiteChrome from "@/components/marketing/SiteChrome";
import PageHeading from "@/components/marketing/PageHeading";
import { NEXT } from "@/lib/feature-status";

export const metadata: Metadata = {
  title: "How it works | SearchScribe",
  description: "From your topic to an editable article and HTML or Markdown export.",
};

const steps = [
  [
    "01",
    "Enter a topic",
    "Give the studio a specific subject or search query. A clear topic makes the first draft more useful.",
  ],
  [
    "02",
    "Generate a draft",
    "The studio looks for web sources first, then writes a structured article and SEO fields from them. Sources have their own tab, and a draft without usable sources is marked Unresearched. Review the result carefully: a first draft can contain mistakes.",
  ],
  [
    "03",
    "Edit with intent",
    "Adjust the article and SEO metadata yourself, or try a rewrite style. Save your changes as a new version.",
  ],
  [
    "04",
    "Add photos and export",
    "Choose credited Wikimedia Commons photos and write their alt text. Restore an earlier version if you need to, then download saved HTML or Markdown with its sources and photo credits.",
  ],
];

export default function HowItWorksPage() {
  return (
    <SiteChrome>
      <PageHeading
        eyebrow="The process"
        title="A practical path from idea to article."
        description="SearchScribe gives you a starting point and keeps the editing decisions in your hands."
      />
      <section className="mx-auto max-w-7xl px-5 py-12 sm:px-8 lg:px-12">
        {steps.map(([number, title, detail]) => (
          <div
            key={number}
            className="grid gap-5 border-b border-stone-300 py-10 md:grid-cols-[.25fr_.7fr_1fr] md:gap-10"
          >
            <span className="text-sm font-semibold text-teal-800">{number} / 04</span>
            <h2 className="font-serif text-3xl">{title}</h2>
            <p className="max-w-xl leading-7 text-slate-600">{detail}</p>
          </div>
        ))}
      </section>
      <section className="bg-[#e7e9e2] px-5 py-16 sm:px-8 lg:px-12">
        <div className="mx-auto max-w-7xl">
          <p className="text-xs font-semibold uppercase tracking-[.2em] text-teal-800">
            Next
          </p>
          <h2 className="mt-4 font-serif text-4xl">What comes next.</h2>
          <ul className="mt-6 grid gap-6 md:grid-cols-3">
            {NEXT.map(({ name, detail }) => (
              <li key={name}>
                <h3 className="font-serif text-2xl">{name}</h3>
                <p className="mt-2 leading-7 text-slate-600">{detail}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </SiteChrome>
  );
}
