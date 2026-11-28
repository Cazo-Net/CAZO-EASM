"use client";

import Link from "next/link";
import { CazoMark } from "@/components/marketing/CazoLogo";

export function ErrorFooter() {
  return (
    <footer className="relative z-10 mt-auto border-t border-border bg-card">
      <div className="mx-auto max-w-4xl px-6 py-8">
        <div className="flex flex-col items-center gap-6 sm:flex-row sm:justify-between">
          <div className="flex items-center gap-2.5">
            <CazoMark className="h-8 w-8" />
            <span className="text-sm font-semibold tracking-tight text-foreground">
              CAZO <span className="font-medium text-muted-foreground">EASM</span>
            </span>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-muted-foreground">
            <Link href="/dashboard" className="hover:text-foreground transition-colors">
              Dashboard
            </Link>
            <Link href="/settings" className="hover:text-foreground transition-colors">
              Settings
            </Link>
            <a
              href="https://status.cazoeasm.io"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-foreground transition-colors"
            >
              System Status
            </a>
            <a
              href="mailto:support@cazoeasm.io"
              className="hover:text-foreground transition-colors"
            >
              Contact Support
            </a>
          </div>
        </div>

        <div className="mt-6 text-center text-[10px] text-muted-foreground">
          &copy; {new Date().getFullYear()} CAZO EASM. All rights reserved.
        </div>
      </div>
    </footer>
  );
}
