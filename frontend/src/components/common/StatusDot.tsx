"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export type Tone = "active" | "success" | "warning" | "danger" | "muted" | "info";

const toneMap: Record<Tone, string> = {
  active: "bg-cyan-signal",
  success: "bg-phosphor",
  warning: "bg-amber",
  danger: "bg-signal-red",
  muted: "bg-muted-foreground",
  info: "bg-cyan-signal",
};

export function StatusDot({
  tone = "muted",
  pulse = false,
  className,
}: {
  tone?: Tone;
  pulse?: boolean;
  className?: string;
}) {
  return (
    <span className={cn("relative inline-flex h-2 w-2", className)}>
      {pulse && (
        <span
          className={cn(
            "absolute inline-flex h-full w-full animate-ping rounded-full opacity-50",
            toneMap[tone]
          )}
        />
      )}
      <span className={cn("relative inline-flex h-2 w-2 rounded-full", toneMap[tone])} />
    </span>
  );
}
