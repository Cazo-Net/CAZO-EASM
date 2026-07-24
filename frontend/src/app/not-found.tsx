"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function NotFound() {
  const router = useRouter();
  const [countdown, setCountdown] = useState(3);

  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          router.back();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [router]);

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center bg-[#09090B] px-6 text-center">
      <div className="flex h-20 w-20 items-center justify-center rounded-2xl border border-cyan-500/20 bg-cyan-500/10">
        <svg className="h-10 w-10 text-cyan-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
        </svg>
      </div>

      <h1 className="mt-8 text-7xl font-black tracking-tighter text-white sm:text-8xl">404</h1>
      <h2 className="mt-4 text-2xl font-bold tracking-tight text-white">Page Not Found</h2>
      <p className="mt-4 max-w-lg text-sm leading-relaxed text-gray-400">
        The page you are looking for does not exist, may have been moved, or the URL is incorrect.
      </p>

      <p className="mt-6 text-sm text-gray-500">
        Redirecting back in <span className="font-mono text-cyan-400">{countdown}</span>s&hellip;
      </p>

      <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
        <button
          onClick={() => router.back()}
          className="inline-flex items-center gap-2 rounded-xl bg-white px-6 py-3 text-sm font-semibold text-black transition-all hover:bg-gray-200"
        >
          Go Back
        </button>
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-2 rounded-xl border border-white/20 bg-white/5 px-6 py-3 text-sm font-semibold text-white transition-all hover:bg-white/10"
        >
          Return Dashboard
        </Link>
      </div>

      <div className="mt-10 flex flex-wrap justify-center gap-2">
        {[
          { label: "Scans", href: "/scans" },
          { label: "Assets", href: "/assets" },
          { label: "Reports", href: "/reports" },
          { label: "Settings", href: "/settings" },
        ].map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-gray-400 transition-colors hover:border-white/20 hover:text-white"
          >
            {link.label}
          </Link>
        ))}
      </div>

      <p className="mt-12 text-xs text-gray-600">
        &copy; {new Date().getFullYear()} CAZO EASM
      </p>
    </div>
  );
}
