import "./globals.css";
import type { Metadata } from "next";
import Providers from "./providers";

export const metadata: Metadata = {
  title: "SearchScribe AI Studio",
  description: "AI-powered article, SEO metadata, and HTML page generator",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-slate-950 text-white antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
