import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CAZO Admin Panel",
  description: "Standalone admin control panel for the CAZO EASM platform",
  icons: {
    icon: "/logo.svg",
    shortcut: "/logo.svg",
    apple: "/logo.svg",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body>{children}</body>
    </html>
  );
}
