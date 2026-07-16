"use client";

import * as React from "react";
import {
  Lightbulb,
  AlertTriangle,
  CheckCircle2,
  ListChecks,
  X,
  RefreshCw,
} from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { StatCard } from "@/components/common/StatCard";
import { SectionCard } from "@/components/common/SectionCard";
import { EmptyState } from "@/components/common/EmptyState";
import {
  getAIRecommendations,
  dismissAIRecommendation,
} from "@/lib/api-ai";
import { getErrorMessage } from "@/lib/api";
import type { AIRecommendation, AIRecordPriority } from "@/types/ai2";

const priorityStyles: Record<AIRecordPriority, string> = {
  critical: "bg-destructive/15 text-destructive border border-destructive/30",
  high: "bg-warning/15 text-warning border border-warning/30",
  medium: "bg-info/15 text-info border border-info/30",
  low: "bg-muted text-muted-foreground border border-border/50",
};

function PriorityBadge({ priority }: { priority: AIRecordPriority }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide ${
        priorityStyles[priority] ?? priorityStyles.medium
      }`}
    >
      {priority}
    </span>
  );
}

export default function AIRecommendationsPage() {
  const [recs, setRecs] = React.useState<AIRecommendation[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [dismissing, setDismissing] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAIRecommendations();
      setRecs(data);
    } catch (err) {
      setError(getErrorMessage(err, "Failed to load recommendations"));
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const handleDismiss = async (id: string) => {
    setDismissing(id);
    try {
      await dismissAIRecommendation(id);
      setRecs((prev) => prev.filter((r) => r.id !== id));
    } catch (err) {
      setError(getErrorMessage(err, "Failed to dismiss recommendation"));
    } finally {
      setDismissing(null);
    }
  };

  const open = recs.filter((r) => r.status !== "dismissed").length;
  const critical = recs.filter(
    (r) => r.status !== "dismissed" && r.priority === "critical"
  ).length;

  return (
    <div className="page-container-md">
      <PageHeader
        title="AI Recommendations"
        description="Evidence-backed, prioritized actions from the AI Intelligence Engine."
        icon={<Lightbulb className="h-5 w-5" />}
        breadcrumbs={[{ label: "AI", href: "/ai" }, { label: "Recommendations" }]}
        actions={
          <button
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-lg border border-border/60 bg-surface-2 px-3 py-2 text-sm font-medium transition-colors hover:bg-surface-3 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label="Total"
          value={recs.length}
          icon={<ListChecks className="h-5 w-5" />}
          accent="brand"
        />
        <StatCard
          label="Open"
          value={open}
          icon={<CheckCircle2 className="h-5 w-5" />}
          accent="success"
        />
        <StatCard
          label="Critical"
          value={critical}
          icon={<AlertTriangle className="h-5 w-5" />}
          accent="danger"
        />
      </div>

      <SectionCard
        title="Recommendations"
        description={`${open} open · ${critical} critical`}
        className="mt-6"
        bodyClassName="p-0"
      >
        {loading ? (
          <div className="flex items-center justify-center px-6 py-12 text-sm text-muted-foreground">
            <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> Loading recommendations…
          </div>
        ) : error ? (
          <div className="px-6 py-10">
            <EmptyState
              icon={<AlertTriangle className="h-6 w-6" />}
              title="Could not load recommendations"
              description={error}
            />
          </div>
        ) : recs.length === 0 ? (
          <div className="px-6 py-10">
            <EmptyState
              icon={<Lightbulb className="h-6 w-6" />}
              title="No recommendations yet"
              description="Run a scan or ask the AI assistant to generate security recommendations."
            />
          </div>
        ) : (
          <ul className="divide-y divide-border/50">
            {recs.map((r) => (
              <li
                key={r.id}
                className="flex items-start gap-4 px-6 py-4 transition-colors hover:bg-surface-2/40"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <PriorityBadge priority={r.priority} />
                    <span className="rounded-full bg-surface-3 px-2 py-0.5 text-xs font-medium text-muted-foreground">
                      {r.category}
                    </span>
                  </div>
                  <h3 className="mt-2 text-sm font-semibold">{r.title}</h3>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {r.description}
                  </p>
                </div>
                <button
                  onClick={() => handleDismiss(r.id)}
                  disabled={dismissing === r.id}
                  className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-border/60 px-2.5 py-1.5 text-xs font-medium transition-colors hover:bg-destructive/10 hover:text-destructive disabled:opacity-50"
                  aria-label="Dismiss recommendation"
                >
                  {dismissing === r.id ? (
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <X className="h-3.5 w-3.5" />
                  )}
                  Dismiss
                </button>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>
    </div>
  );
}
