import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "EdgeSignal — Intraday Intelligence",
  description: "Social attention, news sentiment, and market-confirmed intraday signals for India.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
  openGraph: {
    title: "EdgeSignal — Intraday Intelligence",
    description: "Find the signal before the crowd.",
    images: ["/og-edgesignal.png"],
  },
  twitter: {
    card: "summary_large_image",
    title: "EdgeSignal — Intraday Intelligence",
    description: "Find the signal before the crowd.",
    images: ["/og-edgesignal.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
