"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CazoLogo } from "@/components/marketing/CazoLogo";
import { BookOpen, ArrowLeft } from "lucide-react";
import { cn } from "@/lib/utils";

const DOCS_NAV = [
  { href: "/docs", label: "Overview" },
  { href: "/docs/getting-started", label: "Getting Started" },
  { label: "---", href: "" },
  { href: "/docs/blockchain-intel", label: "Blockchain Intelligence" },
  { href: "/docs/supply-chain", label: "Supply Chain" },
  { href: "/docs/exposure-validation", label: "Exposure Validation" },
  { label: "---", href: "" },
  { href: "/docs/shadow-assets", label: "What is a Shadow Asset?" },
  { href: "/docs/threat-score", label: "Threat Exposure Score" },
  { href: "/docs/unverified-cves", label: 'What "unverified" means' },
  { href: "/docs/evidence-panel", label: "Reading the Evidence Panel" },
  { label: "---", href: "" },
  { href: "/docs/webhooks", label: "Webhooks" },
  { href: "/docs/integrations", label: "Integrations" },
  { label: "---", href: "" },
  { href: "/docs/authorized-scope", label: "Authorized Scope" },
  { href: "/docs/scan-statuses", label: 'Why "blocked by CDN"?' },
  { href: "/docs/glossary", label: "Glossary" },
];

export function DocsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-void/80">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <Link href="/" className="flex items-center gap-2">
            <CazoLogo />
          </Link>
          <Link
            href="/dashboard"
            className="flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to app
          </Link>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-6 py-12 lg:flex lg:gap-16">
        <nav className="mb-8 shrink-0 lg:mb-0 lg:w-56 lg:sticky lg:top-24 lg:self-start">
          <div className="mb-4 flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-phosphor" />
            <span className="text-sm font-semibold text-foreground">
              Documentation
            </span>
          </div>
          <ul className="space-y-0.5">
            {DOCS_NAV.map((link, i) => {
              if (link.label === "---") {
                return <li key={`sep-${i}`} className="my-2 border-t border-border" />;
              }
              const active =
                link.href === "/docs"
                  ? pathname === "/docs"
                  : pathname.startsWith(link.href);
              return (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className={cn(
                      "block rounded-lg px-3 py-1.5 text-sm transition-colors",
                      active
                        ? "bg-phosphor/10 text-phosphor font-medium"
                        : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                    )}
                  >
                    {link.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <main className="min-w-0 flex-1">{children}</main>
      </div>

      <footer className="border-t border-border bg-void">
        <div className="mx-auto flex h-12 max-w-6xl items-center justify-between px-6">
          <p className="font-mono text-[11px] text-muted-foreground">
            &copy; {new Date().getFullYear()} CAZO
          </p>
          <Link
            href="/"
            className="font-mono text-[11px] text-muted-foreground hover:text-foreground"
          >
            cazo.io
          </Link>
        </div>
      </footer>
    </div>
  );
}
