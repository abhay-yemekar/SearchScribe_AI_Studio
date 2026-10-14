import Image from "next/image";

export default function EditorialVisual() {
  return (
    <section
      className="editorial-section section-container"
      aria-label="A thought taking shape"
      data-reveal
    >
      <figure className="editorial-visual">
        <Image
          src="/editorial/thought-taking-shape.webp"
          alt="Sculptural paper folds with a flowing blue ink line on a writer’s desk."
          fill
          sizes="(max-width: 700px) 100vw, (max-width: 1536px) 92vw, 1440px"
          quality={85}
          loading="lazy"
          className="editorial-image"
        />
        <div className="editorial-shade" aria-hidden />
        <figcaption className="editorial-caption">
          <span className="eyebrow">[ A little space for a bigger idea. ]</span>
          <h2>
            Good writing
            <br />
            takes <span className="serif-italic">shape.</span>
          </h2>
          <p>
            A first draft is a beginning.
            <br />
            What you make of it is yours.
          </p>
        </figcaption>
        <span className="editorial-edition eyebrow" aria-hidden>
          SearchScribe / Field notes No. 01
        </span>
      </figure>
    </section>
  );
}
