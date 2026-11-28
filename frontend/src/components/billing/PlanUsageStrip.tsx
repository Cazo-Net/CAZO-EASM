"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";
import { getBillingOverview, LIMIT_LABELS, type BillingOverview, type LimitKey } from "@/lib/api-billing";

/**
 * One line of plan usage ("Root domains 1 of 3 · Scans this month 4 of 100")
 * shown next to forms that use the allowance, so the limit is visible before
 * the customer runs into it. Renders nothing until the data is loaded.
 */
export function PlanUsageStrip({
  metrics,
  className,
  refreshKey,
}: {
  metrics: LimitKey[];
  className?: string;
  /** Change it to reload after the form adds something. */
  refreshKey?: unknown;
}) {
  const { user } = useAuth();
  const [overview, setOverview] = useState<BillingOverview | null>(null);

  useEffect(() => {
    if (!user?.organization_id) return;
    let cancelled = false;
    getBillingOverview()
      .then((o) => !cancelled && setOverview(o))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [user?.organization_id, refreshKey]);

  if (!overview) return null;
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted-foreground",
        className
      )}
    >
      <span>
        <span className="text-foreground">{overview.plan.name}</span> plan
      </span>
      {metrics.map((m) => {
        const u = overview.usage[m];
        if (!u) return null;
        const full = u.limit != null && u.used >= u.limit;
        return (
          <span key={m} className="inline-flex items-center gap-1.5">
            <span
              aria-hidden
              className={cn("h-1.5 w-1.5 rounded-full", full ? "bg-amber-400" : "bg-emerald-400")}
            />
            {LIMIT_LABELS[m]}{" "}
            <span className={cn("font-mono", full ? "text-amber-400" : "text-foreground")}>
              {u.used.toLocaleString()} of {u.limit == null ? "unlimited" : u.limit.toLocaleString()}
            </span>
          </span>
        );
      })}
      <Link href="/billing" className="text-primary hover:underline">
        Usage and plan
      </Link>
    </div>
  );
}
