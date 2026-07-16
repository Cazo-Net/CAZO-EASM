"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  Loader2,
  RefreshCw,
  PlusCircle,
  MinusCircle,
  Pencil,
  Circle,
  Radio,
} from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { StatCard } from "@/components/common/StatCard";
import { SectionCard } from "@/components/common/SectionCard";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/contexts/AuthContext";
import { listChangeFeed, getChangeFeedSummary } from "@/lib/api-changefeed";
import type { ChangeFeedItem, ChangeFeedSummary } from "@/types/changefeed";

function relativeTime(value: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  const diff = Date.now() - d.getTime();
  const sec = Math.round(diff / 1000);
  if (sec < 60) return "just now";
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  if (day < 30) return `${day}d ago`;
  return d.toLocaleDateString();
}

function changeIcon(type: string) {
  switch (type) {
    case "added":
      return <PlusCircle className="h-4 w-4 text-emerald-500" />;
    case "removed":
      return <MinusCircle className="h-4 w-4 text-destructive" />;
    case "modified":
      return <Pencil className="h-4 w-4 text-amber-500" />;
    default:
      return <Circle className="h-4 w-4 text-muted-foreground" />;
  }
}

function changeBadge(
  type: string
): "success" | "destructive" | "warning" | "secondary" {
  switch (type) {
    case "added":
      return "success";
    case "removed":
      return "destructive";
    case "modified":
      return "warning";
    default:
      return "secondary";
  }
}

export default function ChangeFeedPage() {
  const { user, loading: authLoading } = useAuth();
  const orgId = user?.organization_id;

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [items, setItems] = useState<ChangeFeedItem[]>([]);
  const [summary, setSummary] = useState<ChangeFeedSummary | null>(null);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError("");
    try {
      const [feed, sum] = await Promise.all([
        listChangeFeed(50),
        getChangeFeedSummary(),
      ]);
      setItems(feed);
      setSummary(sum);
    } catch {
      setError("Failed to load change feed.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading) load();
  }, [authLoading, load]);

  if (loading || authLoading) {
    return (
      <div className="page-container-md">
        <div className="flex items-center justify-center py-32 text-muted-foreground">
          <Loader2 className="mr-2 h-6 w-6 animate-spin" /> Loading change feed...
        </div>
      </div>
    );
  }

  return (
    <div className="page-container-md">
      <PageHeader
        title="Change Feed"
        description="Continuous stream of changes across your attack surface"
        icon={<Radio className="h-5 w-5" />}
        breadcrumbs={[{ label: "Change Feed" }]}
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => load(true)}
            disabled={refreshing}
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        }
      />

      {error && (
        <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="mb-6 grid grid-cols-3 gap-4">
        <StatCard
          label="Added"
          value={summary?.added ?? 0}
          icon={<PlusCircle className="h-5 w-5" />}
          accent="success"
          hint="last 30 days"
        />
        <StatCard
          label="Removed"
          value={summary?.removed ?? 0}
          icon={<MinusCircle className="h-5 w-5" />}
          accent="danger"
          hint="last 30 days"
        />
        <StatCard
          label="Modified"
          value={summary?.modified ?? 0}
          icon={<Pencil className="h-5 w-5" />}
          accent="warning"
          hint="last 30 days"
        />
      </div>

      <SectionCard
        title="Recent Changes"
        description="Newest first"
        icon={<Activity className="h-4 w-4" />}
      >
        {items.length === 0 ? (
          <EmptyState
            icon={<Activity className="h-8 w-8" />}
            title={orgId ? "No changes yet" : "No organization"}
            description={
              orgId
                ? "Changes to your assets will appear here as scans run."
                : "Join an organization to track changes across your attack surface."
            }
          />
        ) : (
          <div className="max-h-[560px] space-y-2 overflow-y-auto pr-1">
            {items.map((item) => (
              <div
                key={item.id}
                className="flex items-start gap-3 rounded-lg border border-border/40 bg-muted/20 p-3 transition-colors hover:bg-muted/40"
              >
                <div className="mt-0.5">{changeIcon(item.change_type)}</div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <Badge variant={changeBadge(item.change_type)} className="capitalize">
                      {item.change_type}
                    </Badge>
                    <span className="text-xs capitalize text-muted-foreground">
                      {item.entity_type}
                    </span>
                  </div>
                  <p className="mt-1 truncate text-sm font-medium">
                    {item.asset_label || item.entity_key}
                  </p>
                  <p className="truncate font-mono text-xs text-muted-foreground">
                    {item.entity_key}
                  </p>
                </div>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {relativeTime(item.detected_at)}
                </span>
              </div>
            ))}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
