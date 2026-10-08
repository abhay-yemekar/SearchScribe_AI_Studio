import type { Metadata } from "next";
import SiteChrome from "@/components/marketing/SiteChrome";
import PageHeading from "@/components/marketing/PageHeading";

export const metadata: Metadata = {
  title: "Features | SearchScribe",
  description: "Explore the writing tools available now and the features in development.",
};

const available = [
  [
    "Article generation",
    "Create a sectioned draft from a topic, then review it before publication.",
  ],
  [
    "Structured editing",
    "Edit article content and SEO title, description, and keywords.",
  ],
  [
    "Rewrites and history",
    "Apply a rewrite style, save versions, and restore an earlier draft.",
  ],
  ["HTML export", "Preview and download sanitized HTML to publish in your own workflow."],
  [
    "Password and Google sign-in",
    "Enter your workspace using a password or Google. Existing password accounts link Google explicitly from Account.",
  ],
];
const planned = [
  [
    "Verifiable research",
    "Bounded retrieval, visible citations, preserved source links, and an explicit unresearched state.",
  ],
  [
    "Relevant photos",
    "Choose hero and section images with photographer credit, source links, and alt text.",
  ],
  [
    "Account recovery",
    "Password resets, email verification, and tested transactional delivery.",
  ],
  [
    "Reliability controls",
    "Daily quotas, idempotent generation, provider fallback, and Markdown export.",
  ],
];

function FeatureList({ title, items }: { title: string; items: string[][] }) {
  return (
    <section className="mx-auto max-w-7xl px-5 py-14 sm:px-8 lg:px-12">
      <h2 className="font-serif text-4xl">{title}</h2>
      <div className="mt-8 grid gap-4 md:grid-cols-2">
        {items.map(([name, detail]) => (
          <article key={name} className="border-t border-stone-300 py-6">
            <h3 className="font-serif text-2xl">{name}</h3>
            <p className="mt-3 max-w-md leading-7 text-slate-600">{detail}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

export default function FeaturesPage() {
  return (
    <SiteChrome>
      <PageHeading
        eyebrow="The toolkit"
        title="Your ideas, still yours."
        description="A focused workspace for drafting and revision. We distinguish what is available from what is on the roadmap."
      />
      <FeatureList title="Available in the workspace" items={available} />
      <div className="bg-[#e7e9e2]">
        <FeatureList title="In development" items={planned} />
      </div>
    </SiteChrome>
  );
}
