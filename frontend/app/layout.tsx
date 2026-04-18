import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Culinary AI",
  description: "AI-powered restaurant discovery and recommendations"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
