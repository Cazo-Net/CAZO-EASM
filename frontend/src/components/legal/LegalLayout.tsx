import Link from "next/link";
import { CazoLogo } from "@/components/marketing/CazoLogo";

const LEGAL_LINKS = [
  { href: "/legal/terms", label: "Terms of Service" },
  { href: "/legal/authorized-scanning", label: "Authorized Scanning Policy" },
  { href: "/legal/privacy", label: "Privacy Policy" },
  { href: "/legal/acceptable-use", label: "Acceptable Use Policy" },
];

export function LegalLayout({
  children,
  lastUpdated,
}: {
  children: React.ReactNode;
  lastUpdated: string;
}) {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-6">
          <CazoLogo />
          <Link
            href="/"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Back to CAZO
          </Link>
        </div>
      </header>

      <div className="mx-auto max-w-5xl px-6 py-12 lg:flex lg:gap-16">
        <nav className="mb-8 shrink-0 lg:mb-0 lg:w-48 lg:sticky lg:top-24 lg:self-start">
          <p className="mb-3 text-[11px] uppercase tracking-wider text-muted-foreground">
            Legal
          </p>
          <ul className="space-y-1">
            {LEGAL_LINKS.map((link) => (
              <li key={link.href}>
                <Link
                  href={link.href}
                  className="block rounded-lg px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground"
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <main className="min-w-0 flex-1">
          <div className="prose prose-invert prose-sm max-w-none">
            {children}
          </div>
          <p className="mt-12 border-t border-border pt-6 font-mono text-[11px] text-muted-foreground">
            Last updated: {lastUpdated} &middot; These documents should be reviewed
            by a qualified legal professional before being relied upon as binding
            legal agreements.
          </p>
        </main>
      </div>

      <footer className="border-t border-border bg-void">
        <div className="mx-auto flex h-12 max-w-5xl items-center justify-between px-6">
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
