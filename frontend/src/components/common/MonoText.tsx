"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export function MonoText({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span className={cn("font-mono text-[0.85em] tracking-tight", className)}>{children}</span>
  );
}
