"use client";

import Link from "next/link";
import { Shield } from "lucide-react";

export function ErrorFooter() {
  return (
    <footer className="relative z-10 mt-auto border-t border-border bg-card">
      <div className="mx-auto max-w-4xl px-6 py-8">
        <div className="flex flex-col items-center gap-6 sm:flex-row sm:justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-background border border-border">
              <Shield className="h-3.5 w-3.5 text-brand" />
            </div>
            <span className="text-sm font-semibold tracking-tight gradient-text">CAZO EASM</span>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-muted-foreground">
            <Link href="/dashboard" className="hover:text-foreground transition-colors">
              Dashboard
            </Link>
            <Link href="/settings" className="hover:text-foreground transition-colors">
              Settings
            </Link>
            <a
              href="https://status.CAZO EASM.io"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-foreground transition-colors"
            >
              System Status
            </a>
            <a
              href="mailto:support@CAZO EASM.io"
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
