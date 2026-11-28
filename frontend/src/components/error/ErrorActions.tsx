"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import type { ErrorAction } from "@/types/error";

export function ErrorActions({
  actions,
  className,
}: {
  actions: ErrorAction[];
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-center justify-center gap-3", className)}>
      {actions.map((action, i) => {
        const base =
          "inline-flex items-center gap-2 rounded-xl px-6 py-3 text-sm font-semibold transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-brand/50 focus:ring-offset-2 focus:ring-offset-background";
        const variants: Record<string, string> = {
          primary: "bg-brand text-white hover:bg-brand/90 hover:shadow-brand/30",
          secondary:
            "border border-border bg-card text-foreground hover:bg-card hover:border-border",
          ghost: "text-muted-foreground hover:text-foreground hover:bg-muted/30",
        };
        const cls = cn(base, variants[action.variant || "primary"], i === 0 && "order-first");

        if (action.href) {
          return (
            <Link key={action.label} href={action.href} className={cls}>
              {action.icon}
              {action.label}
            </Link>
          );
        }
        return (
          <button key={action.label} onClick={action.onClick} className={cls}>
            {action.icon}
            {action.label}
          </button>
        );
      })}
    </div>
  );
}
