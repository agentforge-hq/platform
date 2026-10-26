import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgentForge | Find the skill you didn’t know to ask for",
  description:
    "Describe your task to discover agent skills for writing, design, engineering, and research. Bring the right capabilities into your agent.",
  openGraph: {
    title: "AgentForge",
    description: "Your goal. The right skill. A new possibility.",
    type: "website",
  },
};
export const viewport: Viewport = { themeColor: "#f7f8f2" };
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
