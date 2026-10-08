type BrandLogoProps = {
  compact?: boolean;
  className?: string;
};

/** The surrounding link supplies the destination; this component supplies its name. */
export default function BrandLogo({ compact = false, className = "" }: BrandLogoProps) {
  return (
    <span className={`brand-logo ${className}`.trim()}>
      <svg
        className="brand-symbol"
        width="36"
        height="36"
        viewBox="0 0 40 40"
        fill="none"
        aria-hidden="true"
        focusable="false"
      >
        <path d="M10 5H4V35H10M30 5H36V35H30" stroke="currentColor" strokeWidth="2.5" />
        <path
          d="M26 12H15V20H25V28H14"
          stroke="currentColor"
          strokeWidth="4"
          strokeLinejoin="miter"
        />
        <path
          className="brand-caret"
          d="M30 12V28"
          stroke="currentColor"
          strokeWidth="2"
        />
      </svg>
      {compact ? (
        <span className="sr-only">SearchScribe AI</span>
      ) : (
        <span className="brand-wordmark">
          SearchScribe<span className="brand-ai"> AI</span>
        </span>
      )}
    </span>
  );
}
