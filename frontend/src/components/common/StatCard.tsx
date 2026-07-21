"use client";

import * as React from "react";
import { TrendingUp, TrendingDown } from "lucide-react";
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

const accentStyles: Record<NonNullable<StatCardProps["accent"]>, { icon: string; border: string }> = {
  brand: { icon: "text-phosphor", border: "from-phosphor/40 to-cyan-signal/20" },
  violet: { icon: "text-neon-violet", border: "from-neon-violet/40 to-phosphor/20" },
  success: { icon: "text-phosphor", border: "from-phosphor/40 to-phosphor/10" },
  warning: { icon: "text-amber", border: "from-amber/40 to-amber/10" },
  danger: { icon: "text-signal-red", border: "from-signal-red/40 to-signal-red/10" },
  info: { icon: "text-cyan-signal", border: "from-cyan-signal/40 to-cyan-signal/10" },
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
  const styles = accentStyles[accent];

  return (
    <Comp
      onClick={onClick}
      className={cn(
        "group relative w-full overflow-hidden rounded-xl border border-border/50 bg-card/50 p-5 text-left backdrop-blur-sm transition-all duration-250",
        "hover:border-border/80 hover:bg-card/70",
        onClick && "hover-glow cursor-pointer",
        className
      )}
    >
      {/* Bottom accent line */}
      <div className={cn("absolute bottom-0 left-0 right-0 h-[2px] bg-gradient-to-r opacity-0 group-hover:opacity-100 transition-opacity duration-300", styles.border)} />

      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <p className="text-[10px] font-medium uppercase tracking-[0.15em] text-muted-foreground/70 font-mono">
            {label}
          </p>
          <p className="mt-2.5 text-3xl font-bold tracking-tight tabular-nums font-mono text-foreground count-up">
            {value}
          </p>
        </div>
        {icon && (
          <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-surface-2/80 border border-border/30", styles.icon)}>
            {icon}
          </div>
        )}
      </div>
      {(delta !== undefined || hint) && (
        <div className="mt-3 flex items-center gap-2 text-xs font-mono">
          {delta !== undefined && (
            <span
              className={cn(
                "inline-flex items-center gap-1 font-medium",
                positive ? "text-phosphor" : "text-signal-red"
              )}
            >
              {positive ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
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
