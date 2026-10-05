import "./globals.css";
import type { Metadata } from "next";
import Providers from "./providers";

export const metadata: Metadata = {
  metadataBase: new URL("https://search-scribe-ai-studio.vercel.app"),
  title: "SearchScribe | An open-source writing studio",
  description:
    "Shape a topic into an article, edit its SEO details, revise with version history, and export HTML.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-[#f5f3ee] text-slate-900 antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
