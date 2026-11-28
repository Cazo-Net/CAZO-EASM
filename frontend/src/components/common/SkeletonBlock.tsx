"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export function SkeletonBlock({ className }: { className?: string }) {
  return <div className={cn("skeleton rounded-lg", className)} />;
}

export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn("space-y-2", className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <SkeletonBlock key={i} className={cn("h-3.5", i === lines - 1 && "w-2/3")} />
      ))}
    </div>
  );
}

export function SkeletonStat({ className }: { className?: string }) {
  return (
    <div className={cn("rounded-xl border border-border bg-card p-5", className)}>
      <SkeletonBlock className="h-3 w-20" />
      <SkeletonBlock className="mt-3 h-8 w-24" />
      <SkeletonBlock className="mt-3 h-3 w-16" />
    </div>
  );
}
