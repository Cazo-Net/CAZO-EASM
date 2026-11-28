"use client";

import Link from "next/link";
import { CazoLogo } from "@/components/marketing/CazoLogo";
import { GhostGuard } from "@/components/error/GhostGuard";
import { useAuth } from "@/contexts/AuthContext";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  // Error details are deliberately not logged or shown; only the digest, which
  // support can match to server logs.
  const { isAuthenticated } = useAuth();
  return (
    <div className={`flex flex-col px-6 ${isAuthenticated ? "min-h-[70vh]" : "min-h-screen bg-background"}`}>
      {!isAuthenticated && (
        <header className="mx-auto flex h-16 w-full max-w-5xl items-center">
          <CazoLogo />
        </header>
      )}

      <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-16">
        <GhostGuard className="mb-6 h-[168px] w-[120px]" />
        <p className="text-sm font-medium text-destructive">Something went wrong</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-foreground">
          This page could not be loaded
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          The problem is on our side and your data is not affected. Try again, and if it keeps
          happening, contact support.
        </p>
        {error?.digest && (
          <p className="mt-3 font-mono text-xs text-muted-foreground">Reference: {error.digest}</p>
        )}

        <div className="mt-8 flex flex-wrap gap-3">
          <button
            onClick={reset}
            className="inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            Try again
          </button>
          <Link
            href="/dashboard"
            className="inline-flex h-10 items-center rounded-md border border-border bg-card px-4 text-sm font-medium text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Go to dashboard
          </Link>
        </div>
      </main>
    </div>
  );
}
