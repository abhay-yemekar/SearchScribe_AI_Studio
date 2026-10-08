import { ImageResponse } from "next/og";

export const alt = "SearchScribe AI — Start with a thought. Leave with a draft.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        width: "100%",
        height: "100%",
        padding: "52px 64px",
        background: "#f6f4ed",
        color: "#17252b",
        fontFamily: "sans-serif",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "18px" }}>
        <svg width="48" height="48" viewBox="0 0 40 40" fill="none">
          <path d="M10 5H4V35H10M30 5H36V35H30" stroke="#17252b" strokeWidth="2.5" />
          <path d="M26 12H15V20H25V28H14" stroke="#17252b" strokeWidth="4" />
          <path d="M30 12V28" stroke="#17252b" strokeWidth="2" />
        </svg>
        <span style={{ fontSize: "31px", fontWeight: 700, letterSpacing: "-1.5px" }}>
          SearchScribe
        </span>
        <span
          style={{
            background: "#e0f06b",
            padding: "5px 9px",
            fontSize: "15px",
            fontWeight: 700,
          }}
        >
          AI
        </span>
      </div>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          fontSize: "88px",
          fontWeight: 700,
          lineHeight: 1.02,
          letterSpacing: "-5px",
        }}
      >
        <span>Start with a thought.</span>
        <span>Leave with a draft.</span>
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderTop: "1px solid #c5cac3",
          paddingTop: "22px",
          fontSize: "18px",
        }}
      >
        <span>An open-source writing studio.</span>
        <span>searchscribe-ai.vercel.app ↗</span>
      </div>
    </div>,
    size,
  );
}
