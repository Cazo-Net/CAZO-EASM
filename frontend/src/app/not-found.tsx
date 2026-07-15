"use client";

import Link from "next/link";
import { Shield } from "lucide-react";

export default function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#09090B] px-4">
      <div className="relative mb-8">
        <div className="absolute inset-0 rounded-full bg-primary/20 blur-3xl" />
        <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl border border-border/50 bg-card/80">
          <Shield className="h-10 w-10 text-primary" />
        </div>
      </div>
      <h1 className="text-6xl font-bold text-foreground mb-2">404</h1>
      <p className="text-lg text-muted-foreground mb-1">Page not found</p>
      <p className="text-sm text-muted-foreground/60 mb-8">The page you are looking for does not exist or has been moved.</p>
      <Link
        href="/"
        className="rounded-lg bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
      >
        Go Home
      </Link>
    </div>
  );
}
