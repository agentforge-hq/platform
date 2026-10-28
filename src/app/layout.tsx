import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { brandPromise, brandTagline } from "@/lib/brand";
import "./globals.css";

const literarySerif = localFont({
  src: "./fonts/CormorantGaramond-latin.woff2",
  variable: "--font-literary",
  weight: "400 600",
  display: "swap",
});

export const metadata: Metadata = {
  title: `AgentForge | ${brandPromise}`,
  description:
    "Describe your task to discover agent skills for writing, design, engineering, and research. Bring the right capabilities into your agent.",
  openGraph: {
    title: `AgentForge | ${brandPromise}`,
    description: brandTagline,
    type: "website",
  },
};
export const viewport: Viewport = { themeColor: "#f8f5ed" };
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${GeistSans.variable} ${GeistMono.variable} ${literarySerif.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
