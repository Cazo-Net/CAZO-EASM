"use client";

import Link from "next/link";
import { CazoLogo } from "@/components/marketing/CazoLogo";
import { useAuth } from "@/contexts/AuthContext";

const LINKS = [
  { label: "Dashboard", href: "/dashboard" },
  { label: "Scans", href: "/scans" },
  { label: "Assets", href: "/assets" },
  { label: "Findings", href: "/vulnerabilities" },
];

export default function NotFound() {
  const { isAuthenticated } = useAuth();
  return (
    <div className={`flex flex-col px-6 ${isAuthenticated ? "min-h-[70vh]" : "min-h-screen bg-background"}`}>
      {!isAuthenticated && (
        <header className="mx-auto flex h-16 w-full max-w-5xl items-center">
          <CazoLogo />
        </header>
      )}

      <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-16">
        <p className="font-mono text-sm text-primary">404</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-foreground">
          This page is not in scope
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          The address may be mistyped, or the page has moved. Nothing was lost; your scans and
          findings are where you left them.
        </p>

        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            href="/dashboard"
            className="inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            Go to dashboard
          </Link>
          <Link
            href="/"
            className="inline-flex h-10 items-center rounded-md border border-border bg-card px-4 text-sm font-medium text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Home
          </Link>
        </div>

        <nav aria-label="Other places" className="mt-10 border-t border-border pt-6">
          <ul className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
            {LINKS.map((l) => (
              <li key={l.href}>
                <Link href={l.href} className="text-muted-foreground transition-colors hover:text-foreground">
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </main>
    </div>
  );
}
