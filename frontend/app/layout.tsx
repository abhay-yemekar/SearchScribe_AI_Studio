import "./globals.css";
import type { Metadata } from "next";
import Providers from "./providers";
import { Manrope, DM_Serif_Display, IBM_Plex_Mono } from "next/font/google";

const sans = Manrope({ subsets: ["latin"], variable: "--font-sans", display: "swap" });
const display = DM_Serif_Display({
  weight: "400",
  style: ["normal", "italic"],
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});
const mono = IBM_Plex_Mono({
  weight: "400",
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://searchscribe-ai.vercel.app"),
  title: "SearchScribe | An open-source writing studio",
  description:
    "Shape a topic into an article, edit its SEO details, revise with version history, and export HTML.",
  icons: { apple: "/brand/apple-touch-icon.png" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body
        className={`${sans.variable} ${display.variable} ${mono.variable} antialiased`}
      >
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
