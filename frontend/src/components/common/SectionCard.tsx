"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface SectionCardProps {
  title?: React.ReactNode;
  description?: React.ReactNode;
  icon?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  /** Kept for API compatibility; the new design uses a single neutral card. */
  accent?: "brand" | "violet" | "none";
}

export function SectionCard({
  title,
  description,
  icon,
  actions,
  children,
  className,
  bodyClassName,
}: SectionCardProps) {
  return (
    <section
      className={cn(
        "relative overflow-hidden rounded-xl border border-border bg-card shadow-elevation-1",
        className
      )}
    >
      {(title || actions) && (
        <header className="flex items-center gap-3 border-b border-border px-5 py-3.5">
          {icon && (
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground [&_svg]:h-4 [&_svg]:w-4">
              {icon}
            </div>
          )}
          <div className="min-w-0 flex-1">
            {title && <h2 className="truncate text-sm font-semibold">{title}</h2>}
            {description && (
              <p className="truncate text-xs text-muted-foreground">{description}</p>
            )}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cn("p-5", bodyClassName)}>{children}</div>
    </section>
  );
}
