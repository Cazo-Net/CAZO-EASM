"use client";

import * as React from "react";
import { ArrowUpRight, ArrowDownRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: React.ReactNode;
  icon?: React.ReactNode;
  delta?: number;
  deltaSuffix?: string;
  hint?: string;
  accent?: "brand" | "violet" | "success" | "warning" | "danger" | "info";
  className?: string;
  onClick?: () => void;
}

const accentStyles: Record<NonNullable<StatCardProps["accent"]>, string> = {
  brand: "text-primary bg-primary/10",
  violet: "text-accent-2 bg-accent-2/10",
  success: "text-success bg-success/10",
  warning: "text-warning bg-warning/10",
  danger: "text-destructive bg-destructive/10",
  info: "text-info bg-info/10",
};

export function StatCard({
  label,
  value,
  icon,
  delta,
  deltaSuffix = "%",
  hint,
  accent = "brand",
  className,
  onClick,
}: StatCardProps) {
  const positive = (delta ?? 0) >= 0;
  const Comp = onClick ? "button" : "div";

  return (
    <Comp
      onClick={onClick}
      className={cn(
        "group relative w-full rounded-xl border border-border bg-card p-5 text-left shadow-elevation-1 transition-colors",
        onClick && "cursor-pointer hover:border-input hover:bg-surface-2",
        className
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-[13px] font-medium text-muted-foreground">{label}</p>
        {icon && (
          <div className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-md [&_svg]:h-4 [&_svg]:w-4", accentStyles[accent])}>
            {icon}
          </div>
        )}
      </div>
      <p className="mt-2 text-[28px] font-semibold leading-none tracking-tight tabular-nums text-foreground">
        {value}
      </p>
      {(delta !== undefined || hint) && (
        <div className="mt-3 flex items-center gap-2 text-xs">
          {delta !== undefined && (
            <span
              className={cn(
                "inline-flex items-center gap-0.5 rounded px-1 py-0.5 font-medium tabular-nums",
                positive ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive"
              )}
            >
              {positive ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
              {Math.abs(delta)}
              {deltaSuffix}
            </span>
          )}
          {hint && <span className="text-muted-foreground">{hint}</span>}
        </div>
      )}
    </Comp>
  );
}
