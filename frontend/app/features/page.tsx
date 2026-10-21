import type { Metadata } from "next";
import SiteChrome from "@/components/marketing/SiteChrome";
import PageHeading from "@/components/marketing/PageHeading";
import { AVAILABLE, NEXT, type FeatureNote } from "@/lib/feature-status";

export const metadata: Metadata = {
  title: "Features | SearchScribe",
  description: "Explore the writing tools available now and what is planned next.",
};

function FeatureList({ title, items }: { title: string; items: FeatureNote[] }) {
  return (
    <section className="mx-auto max-w-7xl px-5 py-14 sm:px-8 lg:px-12">
      <h2 className="font-serif text-4xl">{title}</h2>
      <div className="mt-8 grid gap-4 md:grid-cols-2">
        {items.map(({ name, detail }) => (
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
        description="A focused workspace for drafting and revision. We distinguish what is available from what is planned next."
      />
      <FeatureList title="Available in the workspace" items={AVAILABLE} />
      <div className="bg-[#e7e9e2]">
        <FeatureList title="Planned next" items={NEXT} />
      </div>
    </SiteChrome>
  );
}
