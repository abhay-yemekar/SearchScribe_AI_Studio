import type { ArticleContent } from "@/lib/api/schemas";

function sourceLink(value: string) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password ? url.href : null;
  } catch {
    return null;
  }
}

function displayDate(value: string | null | undefined) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(value);
  const label = date.toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    ...(dateOnly ? {} : { hour: "2-digit", minute: "2-digit" }),
    timeZone: "UTC",
  });
  return dateOnly ? label : `${label} UTC`;
}

export default function ResearchPanel({
  research,
}: {
  research: ArticleContent["research"];
}) {
  const hasSources =
    research?.status === "sources_retrieved" && research.sources.length > 0;
  const retrieved = hasSources ? displayDate(research.retrieved_at) : null;

  return (
    <section
      aria-label="Article sources"
      className="rounded-lg border border-stone-200 bg-white px-4 py-3 text-sm text-slate-600"
    >
      <p role="status" className="leading-relaxed">
        {hasSources ? (
          <>
            <strong className="font-semibold text-[#17252b]">Sources retrieved.</strong>{" "}
            Review the links and claims before publishing. Retrieval does not guarantee
            complete coverage or confirm the latest social post; edits are not
            automatically fact-checked.
          </>
        ) : (
          "Unresearched draft. No live sources are recorded for this version; verify factual and time-sensitive claims before publishing."
        )}
      </p>
      {retrieved ? (
        <p className="mt-2 text-xs">
          Retrieved: <time dateTime={research!.retrieved_at!}>{retrieved}</time>
        </p>
      ) : null}
      {hasSources ? (
        <ol className="mt-3 space-y-2 border-t border-stone-200 pt-3">
          {research.sources.map((source) => {
            const href = sourceLink(source.url);
            const published = displayDate(source.published_at);
            return (
              <li key={source.id} className="min-w-0 break-words">
                <span className="mr-2 font-mono text-xs text-slate-500">
                  [{source.id}]
                </span>
                {href ? (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-teal-700 underline decoration-teal-700/40 underline-offset-4 hover:decoration-teal-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal-700"
                  >
                    {source.title || "Source"}
                  </a>
                ) : (
                  <span>{source.title || "Source"} (link unavailable)</span>
                )}
                {published ? (
                  <p className="mt-1 text-xs">
                    Reported publication/update (estimated):{" "}
                    <time dateTime={source.published_at!}>{published}</time>
                  </p>
                ) : null}
              </li>
            );
          })}
        </ol>
      ) : null}
    </section>
  );
}
