import "./globals.css";

export const metadata = {
  title: "SearchScribe AI Studio",
  description: "AI-powered search-based content generator"
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-black text-white">{children}</body>
    </html>
  );
}
