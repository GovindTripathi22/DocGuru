import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DocGuru — Template-aware document generator",
  description: "Generate documents and presentations using an uploaded template, with output validation.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark h-full antialiased">
      <body className="min-h-full flex flex-col bg-[#0a0a0c] text-zinc-100">{children}</body>
    </html>
  );
}
