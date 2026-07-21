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
  accent = "none",
}: SectionCardProps) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-xl border border-border/40 bg-card/50 backdrop-blur-sm",
        className
      )}
    >
      {accent !== "none" && (
        <div
          className={cn(
            "absolute inset-x-0 top-0 h-[2px]",
            accent === "brand" ? "gradient-brand" : "gradient-violet"
          )}
        />
      )}
      {(title || actions) && (
        <div className="flex items-center gap-3 border-b border-border/30 px-5 py-3.5">
          {icon && (
            <div
              className={cn(
                "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg",
                accent === "violet" ? "bg-neon-violet/10 text-neon-violet" : "bg-phosphor/8 text-phosphor"
              )}
            >
              {icon}
            </div>
          )}
          <div className="min-w-0 flex-1">
            {title && <h2 className="truncate text-sm font-semibold font-display">{title}</h2>}
            {description && (
              <p className="truncate text-[11px] text-muted-foreground/60 font-mono">{description}</p>
            )}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className={cn("p-5", bodyClassName)}>{children}</div>
    </div>
  );
}
