import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DocGuru — Exact Template Inheritance Generator",
  description: "Exact template inheritance and content generation system powered by Gemma",
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
