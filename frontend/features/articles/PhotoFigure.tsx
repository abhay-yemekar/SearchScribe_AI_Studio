import Image from "next/image";
import type { PhotoAsset } from "@/lib/api/schemas";

export default function PhotoFigure({ photo, alt }: { photo: PhotoAsset; alt: string }) {
  return (
    <figure className="my-6 overflow-hidden rounded-xl border border-stone-200 bg-stone-50 font-sans">
      <a
        href={photo.source_url}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={`View ${photo.title} on Wikimedia Commons`}
      >
        <Image
          src={photo.preview_url}
          alt={alt}
          width={photo.width}
          height={photo.height}
          unoptimized
          className="h-auto max-h-128 w-full object-contain"
          referrerPolicy="no-referrer"
        />
      </a>
      <figcaption className="wrap-break-word px-4 py-3 text-xs leading-relaxed text-slate-600">
        <span>{photo.title} — </span>
        <a
          href={photo.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="underline underline-offset-2"
        >
          {photo.creator}
        </a>
        {", "}
        <a
          href={photo.license_url}
          target="_blank"
          rel="noopener noreferrer"
          className="underline underline-offset-2"
        >
          {photo.license_name}
        </a>
        {". Wikimedia Commons."}
      </figcaption>
    </figure>
  );
}
