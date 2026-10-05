import Link from "next/link";

export default function PageHeading({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <section className="border-b border-stone-200">
      <div className="mx-auto max-w-7xl px-5 pb-16 pt-16 sm:px-8 md:pb-24 md:pt-24 lg:px-12">
        <p className="text-xs font-semibold uppercase tracking-[.2em] text-teal-800">
          {eyebrow}
        </p>
        <h1 className="mt-6 max-w-4xl font-serif text-[clamp(3.3rem,7vw,6.5rem)] leading-[1.02] tracking-[-.055em]">
          {title}
        </h1>
        <p className="mt-7 max-w-2xl text-lg leading-8 text-slate-600">{description}</p>
        <Link
          href="/login?mode=signup"
          className="mt-8 inline-flex rounded-full bg-teal-800 px-6 py-3 font-semibold text-white hover:bg-teal-900"
        >
          Start writing ↗
        </Link>
      </div>
    </section>
  );
}
