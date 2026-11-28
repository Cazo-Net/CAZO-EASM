"use client";

import Link from "next/link";
import { ArrowUpRight, Gauge } from "lucide-react";
import { cn } from "@/lib/utils";
import { LIMIT_LABELS, type LimitKey, type PlanLimitDetail } from "@/lib/api-billing";

const METRIC_TITLE: Record<string, string> = {
  root_domains: "Root domain limit reached",
  hosts: "Host limit reached",
  users: "All user seats are taken",
  scans_per_month: "Monthly scan allowance used",
  scan_frequency: "Schedule is more frequent than your plan allows",
};

/**
 * Shown when the API refuses an action with HTTP 402 (plan allowance used up).
 * Explains what happened in plain words and offers the two ways forward:
 * upgrade, or look at usage on the Billing page.
 */
export function PlanLimitNotice({
  detail,
  className,
  compact = false,
}: {
  detail: PlanLimitDetail;
  className?: string;
  compact?: boolean;
}) {
  const meter = detail.metric in LIMIT_LABELS ? LIMIT_LABELS[detail.metric as LimitKey] : null;
  return (
    <div
      role="alert"
      className={cn(
        "rounded-xl border border-amber-500/40 bg-amber-500/[0.08] p-4 text-sm",
        className
      )}
    >
      <div className="flex gap-3">
        <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-amber-500/15 text-amber-400">
          <Gauge className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-medium text-foreground">{METRIC_TITLE[detail.metric] ?? "Plan limit reached"}</p>
          <p className="mt-1 text-muted-foreground">{detail.message}</p>
          {!compact && meter && detail.limit != null && (
            <p className="mt-2 font-mono text-[11px] text-muted-foreground">
              {meter}: {detail.used.toLocaleString()} of {detail.limit.toLocaleString()} on {detail.plan_name}
            </p>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            <Link
              href="/billing/checkout"
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              {detail.plan === "free" ? "Choose a plan" : "Upgrade plan"} <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
            <Link
              href="/billing"
              className="inline-flex items-center rounded-md border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground transition hover:text-foreground"
            >
              View usage
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
