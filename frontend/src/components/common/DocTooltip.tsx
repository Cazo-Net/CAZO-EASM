"use client";

import * as React from "react";
import Link from "next/link";
import { HelpCircle, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";

const DOC_SUMMARIES: Record<string, string> = {
  "shadow-assets":
    "An asset that's probably yours but isn't in your confirmed inventory — discovered through shared IPs, certificates, or ASNs.",
  "threat-score":
    "A composite risk rating based on your attack surface findings. Directional, not absolute.",
  "unverified-cves":
    "Version-correlated: we matched the software version against NVD, but haven't confirmed it's exploitable on your host.",
  "evidence-panel":
    "Shows how an asset was discovered, when it first appeared, and how many times it's been confirmed since.",
  "authorized-scope":
    "A declaration of what you're authorized to scan. Required before CAZO will run any scan.",
  "scan-statuses":
    "Honest status badges: ok, rate-limited, blocked-by-cdn, error. We report failures instead of hiding them.",
};

export function DocTooltip({
  article,
  className,
}: {
  article: string;
  className?: string;
}) {
  const [open, setOpen] = React.useState(false);
  const summary = DOC_SUMMARIES[article];

  return (
    <span
      className={cn("relative inline-flex", className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        className="inline-flex items-center text-muted-foreground/50 transition-colors hover:text-muted-foreground"
        aria-label={`Learn more about ${article.replace(/-/g, " ")}`}
        onClick={() => setOpen(!open)}
      >
        <HelpCircle className="h-3.5 w-3.5" />
      </button>

      {open && (
        <div className="absolute bottom-full left-1/2 z-50 mb-2 w-64 -translate-x-1/2 rounded-xl border border-border/60 bg-card/95 p-3 shadow-elevation-3 backdrop-blur-xl">
          {summary && (
            <p className="text-xs leading-relaxed text-muted-foreground">
              {summary}
            </p>
          )}
          <Link
            href={`/docs/${article}`}
            className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-phosphor hover:underline"
            onClick={() => setOpen(false)}
          >
            Read more
            <ExternalLink className="h-3 w-3" />
          </Link>
          {/* arrow */}
          <div className="absolute -bottom-1 left-1/2 h-2 w-2 -translate-x-1/2 rotate-45 border-b border-r border-border/60 bg-card/95" />
        </div>
      )}
    </span>
  );
}
