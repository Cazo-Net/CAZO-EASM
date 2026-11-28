"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export function Toolbar({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>{children}</div>
  );
}

export interface FilterOption {
  label: string;
  value: string;
}

export function FilterBar({
  filters,
  value,
  onChange,
  className,
}: {
  filters: FilterOption[];
  value: string;
  onChange: (v: string) => void;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-center gap-1 rounded-xl border border-border bg-surface-2 p-1", className)}>
      {filters.map((f) => (
        <button
          key={f.value}
          onClick={() => onChange(f.value)}
          className={cn(
            "rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
            value === f.value
              ? "bg-card text-foreground shadow-elevation-1"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {f.label}
        </button>
      ))}
    </div>
  );
}
