import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Organizer Dashboard",
    template: "%s | Organizer Dashboard",
  },
  description: "Visual interface for document organization and search",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-white text-neutral-800 min-h-screen antialiased">
        {children}
      </body>
    </html>
  );
}
