"use client";

import { useEffect } from "react";
import Link from "next/link";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // No console.error in production — leaks error details
  }, [error]);

  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#09090B] text-white">
        <div className="relative flex min-h-screen flex-col items-center justify-center px-6 text-center">
          <div className="flex h-20 w-20 items-center justify-center rounded-2xl border border-red-500/20 bg-red-500/10">
            <svg className="h-10 w-10 text-red-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
            </svg>
          </div>

          <h1 className="mt-8 text-7xl font-black tracking-tighter sm:text-8xl">500</h1>
          <h2 className="mt-4 text-2xl font-bold tracking-tight">Unexpected System Error</h2>
          <p className="mt-4 max-w-lg text-sm leading-relaxed text-gray-400">
            A critical error occurred. Please try refreshing the page.
          </p>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <button
              onClick={reset}
              className="inline-flex items-center gap-2 rounded-xl bg-white px-6 py-3 text-sm font-semibold text-black transition-all hover:bg-gray-200"
            >
              Try Again
            </button>
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 rounded-xl border border-white/20 bg-white/5 px-6 py-3 text-sm font-semibold text-white transition-all hover:bg-white/10"
            >
              Dashboard
            </Link>
          </div>

          <p className="mt-12 text-xs text-gray-600">
            &copy; {new Date().getFullYear()} CAZO EASM
          </p>
        </div>
      </body>
    </html>
  );
}
