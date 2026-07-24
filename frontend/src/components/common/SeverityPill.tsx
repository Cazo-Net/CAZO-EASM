"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export type Severity = "critical" | "high" | "medium" | "low" | "info" | "unknown";

const severityMap: Record<Severity, { label: string; cls: string; dotCls: string }> = {
  critical: {
    label: "Critical",
    cls: "bg-signal-red/12 text-signal-red ring-signal-red/25 shadow-glow-danger-sm",
    dotCls: "bg-signal-red shadow-[0_0_6px_2px_hsl(var(--sev-critical)/0.4)]",
  },
  high: {
    label: "High",
    cls: "bg-amber/12 text-amber ring-amber/25",
    dotCls: "bg-amber",
  },
  medium: {
    label: "Medium",
    cls: "bg-warning/12 text-warning ring-warning/25",
    dotCls: "bg-warning",
  },
  low: {
    label: "Low",
    cls: "bg-cyan-signal/10 text-cyan-signal ring-cyan-signal/20",
    dotCls: "bg-cyan-signal",
  },
  info: {
    label: "Info",
    cls: "bg-muted-foreground/10 text-muted-foreground ring-border",
    dotCls: "bg-muted-foreground",
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
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold font-mono ring-1 ring-inset",
        s.cls,
        className
      )}
    >
      {showDot && (
        <span className={cn("h-1.5 w-1.5 rounded-full", s.dotCls)} />
      )}
      {s.label}
    </span>
  );
}
