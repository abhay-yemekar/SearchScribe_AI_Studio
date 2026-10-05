import type { Metadata } from "next";
import SiteChrome from "@/components/marketing/SiteChrome";
import PageHeading from "@/components/marketing/PageHeading";

export const metadata: Metadata = {
  title: "Example | SearchScribe",
  description: "A clearly labeled example of the SearchScribe writing workflow.",
};

export default function ExamplePage() {
  return (
    <SiteChrome>
      <PageHeading
        eyebrow="A worked example"
        title="From a topic to a draft you can own."
        description="This editorial walkthrough uses an illustrative Kerala query. It is sample copy, not a live research result or travel recommendation."
      />
      <article className="mx-auto grid max-w-7xl gap-10 px-5 py-16 sm:px-8 md:grid-cols-[.55fr_1fr] lg:px-12">
        <aside>
          <p className="text-xs font-semibold uppercase tracking-[.2em] text-teal-800">
            Starting point
          </p>
          <p className="mt-3 font-serif text-3xl">“Things to do in Kerala”</p>
          <p className="mt-5 leading-7 text-slate-600">
            Enter a topic, generate a draft, then check every claim and place name before
            publishing. Current generation does not provide verified citations.
          </p>
        </aside>
        <div className="border border-stone-300 bg-white p-7 shadow-[12px_12px_0_#e1e4dc] sm:p-10">
          <p className="text-xs font-semibold uppercase tracking-[.2em] text-teal-800">
            Illustrative draft excerpt
          </p>
          <h2 className="mt-5 font-serif text-4xl leading-tight">
            A first look at Kerala
          </h2>
          <p className="mt-6 leading-8 text-slate-700">
            Kerala offers many kinds of journeys. A draft might open with its backwaters,
            move to the highland landscape around Munnar, and close with ideas for a
            slower coastal itinerary.
          </p>
          <p className="mt-5 leading-8 text-slate-700">
            An editor would now verify the details, improve the structure, add original
            perspective, and decide what belongs in the final article.
          </p>
          <div className="mt-8 border-t border-stone-200 pt-5 text-sm text-slate-600">
            <strong className="text-slate-900">Next in the workspace:</strong> edit the
            copy, review SEO fields, save a version, and export HTML.
          </div>
        </div>
      </article>
      <section className="mx-auto max-w-7xl px-5 pb-20 sm:px-8 lg:px-12">
        <h2 className="font-serif text-3xl">Common questions</h2>
        <div className="mt-7 grid gap-8 md:grid-cols-2">
          <div>
            <h3 className="font-semibold">Is SearchScribe free?</h3>
            <p className="mt-2 leading-7 text-slate-600">
              The project is an open-source, noncommercial beta. AI generation depends on
              available service capacity.
            </p>
          </div>
          <div>
            <h3 className="font-semibold">Can I publish a draft as-is?</h3>
            <p className="mt-2 leading-7 text-slate-600">
              Review facts, rights, tone, and SEO before publishing. Generated text is a
              starting point, not a verified source.
            </p>
          </div>
          <div>
            <h3 className="font-semibold">Does it include sources and photos?</h3>
            <p className="mt-2 leading-7 text-slate-600">
              Not yet. Traceable research and credited photo selection are in development.
            </p>
          </div>
          <div>
            <h3 className="font-semibold">Where can I follow development?</h3>
            <p className="mt-2 leading-7 text-slate-600">
              The{" "}
              <a
                className="underline hover:text-teal-800"
                href="https://github.com/abhay-yemekar/SearchScribe_AI_Studio"
              >
                GitHub repository
              </a>{" "}
              tracks the code and changes.
            </p>
          </div>
        </div>
      </section>
    </SiteChrome>
  );
}
