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
    <section className="inner-heading">
      <div className="section-container" data-reveal>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{description}</p>
        <Link href="/login?mode=signup" className="button">
          Start writing ↗
        </Link>
      </div>
    </section>
  );
}
