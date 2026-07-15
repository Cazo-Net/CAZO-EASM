import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/Providers";
import { ClientLayout } from "@/components/ClientLayout";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: {
    default: "AttackSec - External Attack Surface Management Platform",
    template: "%s | AttackSec",
  },
  description:
    "Discover every subdomain, open port, certificate, and vulnerability across your entire external perimeter. Automated reconnaissance in 60 seconds. Enterprise-grade EASM platform.",
  keywords: [
    "attack surface management",
    "EASM",
    "external attack surface",
    "subdomain discovery",
    "vulnerability scanning",
    "security monitoring",
    "penetration testing",
    "reconnaissance",
    "cybersecurity",
    "asset discovery",
    "port scanning",
    "SSL monitoring",
  ],
  authors: [{ name: "AttackSec" }],
  creator: "AttackSec",
  publisher: "AttackSec",
  metadataBase: new URL("https://attacksec.io"),
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "https://attacksec.io",
    siteName: "AttackSec",
    title: "AttackSec - External Attack Surface Management Platform",
    description:
      "Know what's exposed before attackers do. Discover every subdomain, open port, certificate, and vulnerability across your entire external perimeter.",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "AttackSec - External Attack Surface Management",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "AttackSec - External Attack Surface Management Platform",
    description:
      "Know what's exposed before attackers do. Automated reconnaissance in 60 seconds.",
    images: ["/og-image.png"],
    creator: "@attacksec",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  icons: {
    icon: "/icon.ico",
    shortcut: "/icon.ico",
    apple: "/icon.ico",
  },
  verification: {
    google: "your-google-verification-code",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const structuredData = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "AttackSec",
    applicationCategory: "SecurityApplication",
    operatingSystem: "Web",
    description:
      "External Attack Surface Management Platform. Discover every subdomain, open port, certificate, and vulnerability across your entire external perimeter.",
    url: "https://attacksec.io",
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "USD",
    },
    aggregateRating: {
      "@type": "AggregateRating",
      ratingValue: "4.8",
      ratingCount: "500",
    },
  };

  return (
    <html lang="en" className={inter.variable}>
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
        />
      </head>
      <body className="antialiased">
        <Providers>
          <ClientLayout>{children}</ClientLayout>
        </Providers>
      </body>
    </html>
  );
}
