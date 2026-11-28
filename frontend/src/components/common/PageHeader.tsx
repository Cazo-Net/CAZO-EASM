"use client";

import * as React from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

export interface Crumb {
  label: string;
  href?: string;
}

interface PageHeaderProps {
  title: React.ReactNode;
  description?: React.ReactNode;
  icon?: React.ReactNode;
  breadcrumbs?: Crumb[];
  actions?: React.ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  description,
  icon,
  breadcrumbs,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div className={cn("mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between", className)}>
      <div className="min-w-0">
        {breadcrumbs && breadcrumbs.length > 0 && (
          <nav aria-label="Breadcrumb" className="mb-2 flex items-center gap-1 text-xs text-muted-foreground">
            {breadcrumbs.map((c, i) => (
              <React.Fragment key={`${c.label}-${i}`}>
                {i > 0 && <ChevronRight className="h-3 w-3 opacity-50" aria-hidden="true" />}
                {c.href ? (
                  <Link href={c.href} className="transition-colors hover:text-foreground">
                    {c.label}
                  </Link>
                ) : (
                  <span className="text-foreground/80" aria-current="page">{c.label}</span>
                )}
              </React.Fragment>
            ))}
          </nav>
        )}
        <div className="flex items-center gap-3">
          {icon && (
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-card text-primary [&_svg]:h-[18px] [&_svg]:w-[18px]">
              {icon}
            </div>
          )}
          <div className="min-w-0">
            <h1 className="truncate text-[22px] font-semibold leading-tight tracking-tight">{title}</h1>
            {description && (
              <p className="mt-1 text-sm text-muted-foreground">{description}</p>
            )}
          </div>
        </div>
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
