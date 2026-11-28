"use client";

/**
 * Shared layout for sign-in, sign-up and password pages: the form on the
 * left, a quiet brand panel on the right (hidden on small screens).
 */

import * as React from "react";
import { Check } from "lucide-react";
import { CazoLogo } from "@/components/marketing/CazoLogo";
import { AttackSurfaceArt } from "@/components/auth/AttackSurfaceArt";

const POINTS = [
  { t: "Evidence with every finding", d: "See how, when and by which scan each asset was discovered." },
  { t: "Nothing to install", d: "CAZO works from the outside, the way an attacker would." },
  { t: "Only what you're authorized to scan", d: "Scopes keep scanning inside the assets you own." },
];

export function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div className="dark flex h-full bg-background text-foreground">
      {/* Form column */}
      <div className="flex min-w-0 flex-1 flex-col overflow-y-auto">
        <header className="flex h-16 shrink-0 items-center px-6 md:px-10">
          <CazoLogo />
        </header>
        <main className="flex flex-1 items-center justify-center px-6 py-8">
          <div className="w-full max-w-[380px]">
            <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
            {subtitle && <p className="mt-2 text-sm text-muted-foreground">{subtitle}</p>}
            <div className="mt-8">{children}</div>
            {footer && <div className="mt-6 space-y-2 text-sm text-muted-foreground">{footer}</div>}
          </div>
        </main>
        <footer className="shrink-0 px-6 py-5 text-xs text-muted-foreground md:px-10">
          © {new Date().getFullYear()} CAZO EASM · Scan only assets you own or are authorized to test.
        </footer>
      </div>

      {/* Brand panel */}
      <aside
        aria-hidden="true"
        className="relative hidden w-[44%] max-w-[640px] shrink-0 overflow-hidden border-l border-border bg-card lg:flex lg:flex-col lg:justify-center lg:px-14"
      >
        <div
          className="pointer-events-none absolute inset-0 opacity-40"
          style={{
            backgroundImage:
              "linear-gradient(to right, hsl(var(--border)) 1px, transparent 1px), linear-gradient(to bottom, hsl(var(--border)) 1px, transparent 1px)",
            backgroundSize: "48px 48px",
            maskImage: "radial-gradient(ellipse 80% 70% at 70% 30%, #000 20%, transparent 75%)",
            WebkitMaskImage: "radial-gradient(ellipse 80% 70% at 70% 30%, #000 20%, transparent 75%)",
          }}
        />
        <div className="pointer-events-none absolute -right-40 -top-40 h-[480px] w-[480px] rounded-full bg-primary/20 blur-[130px]" />
        <div className="relative">
          {/* Hidden on short screens so the text is never pushed out of view. */}
          <AttackSurfaceArt className="-ml-4 mb-8 w-full max-w-[520px] [@media(max-height:820px)]:hidden" />
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">
            External attack surface management
          </p>
          <p className="mt-4 text-3xl font-semibold leading-tight tracking-tight">
            You can&apos;t defend what you forgot you own.
          </p>
          <ul className="mt-8 space-y-5">
            {POINTS.map((p) => (
              <li key={p.t} className="flex gap-3">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
                  <Check className="h-3 w-3" />
                </span>
                <div>
                  <p className="text-sm font-medium">{p.t}</p>
                  <p className="mt-0.5 text-sm text-muted-foreground">{p.d}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  );
}

/** Inline error banner used by the auth forms. */
export function AuthError({ children }: { children: React.ReactNode }) {
  return (
    <div role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-sm text-destructive">
      {children}
    </div>
  );
}
