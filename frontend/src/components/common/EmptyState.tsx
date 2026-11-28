"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-surface-2 px-6 py-12 text-center",
        className
      )}
    >
      {icon && (
        <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground">
          {icon}
        </div>
      )}
      <p className="text-sm font-semibold">{title}</p>
      {description && (
        <p className="mt-1 max-w-sm text-[13px] leading-relaxed text-muted-foreground">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
