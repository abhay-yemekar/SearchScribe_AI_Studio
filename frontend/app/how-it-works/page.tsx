import type { Metadata } from "next";
import SiteChrome from "@/components/marketing/SiteChrome";
import PageHeading from "@/components/marketing/PageHeading";

export const metadata: Metadata = {
  title: "How it works | SearchScribe",
  description: "From your topic to an editable article and HTML export.",
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
    "The AI creates a structured article and SEO fields. Generation needs a working backend and model key.",
  ],
  [
    "03",
    "Edit with intent",
    "Adjust the article and SEO metadata yourself, or try a rewrite style. Save your changes as a new version.",
  ],
  [
    "04",
    "Review and export",
    "Restore an earlier version if you need to. Preview and download sanitized HTML for publication elsewhere.",
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
            In development
          </p>
          <h2 className="mt-4 font-serif text-4xl">
            Research and imagery belong in the workflow.
          </h2>
          <p className="mt-4 max-w-2xl leading-7 text-slate-600">
            The planned research step will expose source links and mark drafts when
            retrieval fails. Planned image selection will include photo credit, source
            links, and editable alt text. Neither step is shipped yet.
          </p>
        </div>
      </section>
    </SiteChrome>
  );
}
