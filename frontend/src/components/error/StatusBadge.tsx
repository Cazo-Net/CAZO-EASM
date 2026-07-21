"use client";

import { cn } from "@/lib/utils";
import type { ErrorSeverity } from "@/types/error";

const severityStyles: Record<ErrorSeverity, string> = {
  error: "bg-destructive/10 text-destructive border-destructive/20",
  warning: "bg-warning/10 text-warning border-warning/20",
  info: "bg-info/10 text-info border-info/20",
  maintenance: "bg-accent-2/10 text-accent-2 border-accent-2/20",
};

export function StatusBadge({
  severity,
  label,
  className,
}: {
  severity: ErrorSeverity;
  label: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium",
        severityStyles[severity],
        className
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {label}
    </span>
  );
}
