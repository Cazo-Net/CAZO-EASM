"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { UsageMetric } from "@/types";

interface UsageMeterProps {
  name: string;
  metric: UsageMetric;
  className?: string;
}

const labelMap: Record<string, string> = {
  scans_per_month: "Scans",
  assets: "Assets",
  projects: "Projects",
  team_members: "Team Members",
  api_keys: "API Keys",
  reports_per_month: "Reports",
  alerts: "Alerts",
  data_retention_days: "Data Retention",
  exports_per_month: "Exports",
};

export function UsageMeter({ name, metric, className }: UsageMeterProps) {
  const label = labelMap[name] || name;
  const pct = metric.unlimited ? 0 : metric.percentage;

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-foreground">{label}</span>
        <span className="text-sm text-muted-foreground">
          {metric.unlimited ? (
            <span className="text-brand">Unlimited</span>
          ) : (
            <>
              {metric.current.toLocaleString()} / {metric.limit.toLocaleString()}
              {metric.percentage > 80 && (
                <span className="ml-2 text-warning">
                  ({Math.round(100 - metric.percentage)}% left)
                </span>
              )}
            </>
          )}
        </span>
      </div>
      {!metric.unlimited && (
        <Progress
          value={pct}
          className={cn(
            "h-2",
            pct > 90 && "[&>div]:bg-destructive",
            pct > 70 && pct <= 90 && "[&>div]:bg-warning",
            pct <= 70 && "[&>div]:bg-brand"
          )}
        />
      )}
    </div>
  );
}

interface UsageCardProps {
  usage: Record<string, UsageMetric>;
  periodStartsAt?: string;
  periodEndsAt?: string;
  onRefresh?: () => void;
  refreshing?: boolean;
  className?: string;
}

export function UsageCard({
  usage,
  periodStartsAt,
  periodEndsAt,
  onRefresh,
  refreshing,
  className,
}: UsageCardProps) {
  return (
    <Card className={className}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
        <CardTitle className="text-base font-semibold">Usage</CardTitle>
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={refreshing}
            className="text-sm text-brand hover:underline disabled:opacity-50"
          >
            {refreshing ? "Refreshing..." : "Refresh"}
          </button>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {periodStartsAt && periodEndsAt && (
          <p className="text-xs text-muted-foreground mb-4">
            Billing period: {new Date(periodStartsAt).toLocaleDateString()} -{" "}
            {new Date(periodEndsAt).toLocaleDateString()}
          </p>
        )}
        {Object.entries(usage).map(([key, metric]) => (
          <UsageMeter key={key} name={key} metric={metric} />
        ))}
      </CardContent>
    </Card>
  );
}
