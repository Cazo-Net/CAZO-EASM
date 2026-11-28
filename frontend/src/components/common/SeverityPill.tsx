"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export type Severity = "critical" | "high" | "medium" | "low" | "info" | "unknown";

/* One severity scale used everywhere (tables, cards, charts). Colours come
   from the --sev-* tokens in globals.css. */
const severityMap: Record<Severity, { label: string; cls: string; dotCls: string }> = {
  critical: {
    label: "Critical",
    cls: "bg-severity-critical/10 text-severity-critical ring-severity-critical/30",
    dotCls: "bg-severity-critical",
  },
  high: {
    label: "High",
    cls: "bg-severity-high/10 text-severity-high ring-severity-high/30",
    dotCls: "bg-severity-high",
  },
  medium: {
    label: "Medium",
    cls: "bg-severity-medium/10 text-severity-medium ring-severity-medium/30",
    dotCls: "bg-severity-medium",
  },
  low: {
    label: "Low",
    cls: "bg-severity-low/10 text-severity-low ring-severity-low/30",
    dotCls: "bg-severity-low",
  },
  info: {
    label: "Info",
    cls: "bg-severity-info/10 text-severity-info ring-severity-info/25",
    dotCls: "bg-severity-info",
  },
  unknown: {
    label: "Unknown",
    cls: "bg-muted text-muted-foreground ring-border",
    dotCls: "bg-muted-foreground",
  },
};

export function SeverityPill({
  severity,
  className,
  showDot = true,
}: {
  severity: string;
  className?: string;
  showDot?: boolean;
}) {
  const s = severityMap[(severity?.toLowerCase() as Severity)] ?? severityMap.unknown;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset",
        s.cls,
        className
      )}
    >
      {showDot && <span className={cn("h-1.5 w-1.5 rounded-full", s.dotCls)} aria-hidden="true" />}
      {s.label}
    </span>
  );
}
