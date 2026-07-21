"use client";

import * as React from "react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

export function TrendBadge({
  value,
  suffix = "%",
  className,
}: {
  value: number;
  suffix?: string;
  className?: string;
}) {
  const flat = value === 0;
  const positive = value > 0;
  const Icon = flat ? Minus : positive ? TrendingUp : TrendingDown;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium tabular-nums font-mono",
        flat && "bg-muted/50 text-muted-foreground",
        positive && "bg-phosphor/10 text-phosphor",
        !flat && !positive && "bg-signal-red/10 text-signal-red",
        className
      )}
    >
      <Icon className="h-3 w-3" />
      {positive ? "+" : ""}
      {value}
      {suffix}
    </span>
  );
}
