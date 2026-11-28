import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/Providers";
import { ClientLayout } from "@/components/ClientLayout";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
});


export const metadata: Metadata = {
  title: {
    default: "CAZO - External Attack Surface Management",
    template: "%s | CAZO",
  },
  description:
    "CAZO maps your external attack surface — subdomains, open ports, certificates, services and misconfigurations — with the evidence behind every finding, including the shadow assets you forgot you own.",
  keywords: [
    "attack surface management",
    "EASM",
    "external attack surface",
    "shadow assets",
    "subdomain discovery",
    "asset discovery",
    "port scanning",
    "certificate monitoring",
    "security monitoring",
    "cybersecurity",
  ],
  authors: [{ name: "CAZO" }],
  creator: "CAZO",
  publisher: "CAZO",
  metadataBase: new URL("https://cazoeasm.io"),
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "https://cazoeasm.io",
    siteName: "CAZO",
    title: "CAZO - External Attack Surface Management",
    description:
      "You can't defend what you forgot you own. CAZO maps your external attack surface with the evidence behind every finding.",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "CAZO - External Attack Surface Management",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "CAZO - External Attack Surface Management",
    description:
      "You can't defend what you forgot you own. Map your external attack surface with evidence behind every finding.",
    images: ["/og-image.png"],
    creator: "@cazo",
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
    icon: "/logo.svg",
    shortcut: "/logo.svg",
    apple: "/logo.svg",
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
    name: "CAZO",
    applicationCategory: "SecurityApplication",
    operatingSystem: "Web",
    description:
      "External Attack Surface Management. CAZO maps subdomains, open ports, certificates, services and misconfigurations across your external perimeter, with the evidence behind every finding.",
    url: "https://cazoeasm.io",
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "USD",
    },
  };

  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`} style={{ height: "100%" }}>
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
        />
      </head>
      <body className="antialiased font-sans" style={{ height: "100%", overflow: "hidden" }}>
        <Providers>
          <ClientLayout>{children}</ClientLayout>
        </Providers>
      </body>
    </html>
  );
}
