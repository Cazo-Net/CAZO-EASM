"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  History,
  Calendar,
  Bookmark,
  GitBranch,
  TrendingUp,
  Filter,
  Sparkles,
  Download,
  Loader2,
  ChevronDown,
  AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PageHeader } from "@/components/common/PageHeader";
import { useAuth } from "@/contexts/AuthContext";
import {
  ReplayProvider,
  useReplay,
  Timeline,
  ReplayControls,
  HistoricalDashboard,
  ChangeDetection,
  ExposureEvolution,
  Bookmarks,
  ReplayFilters,
  EventMarkers,
} from "@/components/replay";
import type { HistoricalSnapshot, TimelineEvent, ExposureEvolution as ExposureEvolutionType } from "@/types/replay";
import type { ReplaySnapshot } from "@/types/replay2";
import { getReplayTimeline } from "@/lib/api-replay";
import { exportToCSV } from "@/lib/api";

function mapSnapshotToHistorical(s: ReplaySnapshot, index: number): HistoricalSnapshot {
  const ts = s.completed_at || s.started_at || new Date().toISOString();
  return {
    timestamp: ts,
    scan_id: s.scan_id,
    scan_name: `Scan ${new Date(ts).toLocaleDateString()}`,
    domain: s.domain,
    assets: [],
    total_assets: s.subdomain_count,
    total_subdomains: s.subdomain_count,
    total_ports: s.port_count,
    total_certificates: 0,
    total_technologies: 0,
    exposure_score: s.overall_risk_score ?? 0,
    risk_score: s.overall_risk_score ?? 0,
    critical_count: s.critical_count,
    high_count: s.high_count,
    medium_count: s.medium_count,
    low_count: s.low_count,
  };
}

function buildEvents(scans: ReplaySnapshot[]): TimelineEvent[] {
  return scans.map((s, i) => {
    const ts = s.completed_at || s.started_at || new Date().toISOString();
    const severity = s.critical_count > 0 ? "warning" : "success";
    return {
      id: `scan-${s.scan_id}`,
      timestamp: ts,
      type: "scan_completed",
      title: i === 0 ? "First Scan Completed" : "Scan Completed",
      description: `Scan for ${s.domain} — ${s.subdomain_count} subdomains, ${s.critical_count} critical findings.`,
      severity: severity as "warning" | "success",
      metadata: {},
    };
  });
}

function buildExposureHistory(scans: HistoricalSnapshot[]): ExposureEvolutionType[] {
  return scans.map((s, i) => ({
    timestamp: s.timestamp,
    score: s.exposure_score,
    delta: i > 0 ? s.exposure_score - scans[i - 1].exposure_score : 0,
    reasons: i > 0
      ? s.exposure_score > scans[i - 1].exposure_score
        ? ["New assets discovered", "Configuration changes detected"]
        : s.exposure_score < scans[i - 1].exposure_score
        ? ["Vulnerabilities remediated", "Assets hardened"]
        : []
      : ["Initial scan baseline"],
    assets_count: s.total_assets,
    critical_count: s.critical_count,
  }));
}

function ReplayContent() {
  const { state, initData, setTimestamp, setFromTimestamp, setToTimestamp } = useReplay();
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<"dashboard" | "changes" | "exposure" | "events">("dashboard");
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (loaded) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await getReplayTimeline(user?.organization_id || undefined);
        if (cancelled) return;
        const historical = data.snapshots.map(mapSnapshotToHistorical);
        const events = buildEvents(data.snapshots);
        const exposure = buildExposureHistory(historical);
        initData(historical, events, exposure);
        setLoaded(true);
      } catch (err) {
        if (!cancelled) setError("Failed to load replay timeline.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loaded, initData, user?.organization_id]);

  const tabs = [
    { id: "dashboard" as const, label: "Dashboard", icon: History },
    { id: "changes" as const, label: "Changes", icon: GitBranch },
    { id: "exposure" as const, label: "Exposure", icon: TrendingUp },
    { id: "events" as const, label: "Events", icon: Calendar },
  ];

  if (state.loading || (!loaded && !error)) {
    return (
      <div className="page-container-lg">
        <PageHeader
          title="Exposure Replay"
          description="Your surface, before and after. See what changed between scans."
          icon={<History className="h-5 w-5" />}
        />
        <div className="flex items-center justify-center gap-2 py-24 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading replay timeline…
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-container-lg">
        <PageHeader
          title="Exposure Replay"
          description="Your surface, before and after. See what changed between scans."
          icon={<History className="h-5 w-5" />}
        />
        <div className="flex flex-col items-center gap-2 py-24 text-sm text-muted-foreground">
          <AlertCircle className="h-6 w-6 text-destructive" />
          {error}
        </div>
      </div>
    );
  }

  if (state.scans.length === 0) {
    return (
      <div className="page-container-lg">
        <PageHeader
          title="Exposure Replay"
          description="Your surface, before and after. See what changed between scans."
          icon={<History className="h-5 w-5" />}
        />
        <div className="flex flex-col items-center gap-2 py-24 text-center text-sm text-muted-foreground">
          <History className="h-6 w-6 text-muted-foreground" />
          No completed scans yet. Run one to see how your surface changed.
        </div>
      </div>
    );
  }

  return (
    <div className="page-container-lg">
      <PageHeader
        title="Exposure Replay"
        description="Your surface, before and after. See what changed between scans."
        icon={<History className="h-5 w-5" />}
        actions={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() =>
                exportToCSV(
                  state.scans.map((s) => ({
                    completed_at: s.timestamp,
                    domain: s.domain,
                    subdomains: s.total_subdomains,
                    ports: s.total_ports,
                    risk_score: s.risk_score,
                    critical: s.critical_count,
                    high: s.high_count,
                    medium: s.medium_count,
                    low: s.low_count,
                  })),
                  "exposure-timeline"
                )
              }
              className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-xs font-medium text-muted-foreground hover:bg-card transition-colors">
              <Download className="h-3.5 w-3.5" />
              Export
            </button>
          </div>
        }
      />

      <div className="py-6 space-y-6">
        {/* Timeline bar */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-border bg-card p-4"
        >
          <Timeline />
          <div className="mt-3">
            <ReplayControls />
          </div>
        </motion.div>

        {/* Main content area */}
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          {/* Left: Main panel */}
          <div className="space-y-6">
            {/* Tab navigation */}
            <div className="flex gap-1 rounded-xl border border-border bg-card p-1">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition-colors flex-1 justify-center",
                    activeTab === tab.id
                      ? "bg-brand/10 text-brand"
                      : "text-muted-foreground hover:bg-muted/30 hover:text-foreground"
                  )}
                >
                  <tab.icon className="h-3.5 w-3.5" />
                  <span className="hidden sm:inline">{tab.label}</span>
                </button>
              ))}
            </div>

            {/* Tab content */}
            {activeTab === "dashboard" && <HistoricalDashboard />}
            {activeTab === "changes" && (
              <div className="rounded-xl border border-border bg-card p-5">
                <ChangeDetection />
              </div>
            )}
            {activeTab === "exposure" && (
              <div className="rounded-xl border border-border bg-card p-5">
                <ExposureEvolution />
              </div>
            )}
            {activeTab === "events" && (
              <div className="rounded-xl border border-border bg-card p-5">
                <EventMarkers />
              </div>
            )}

            {/* Current scan info */}
            {state.selectedScan && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="rounded-xl border border-border bg-card p-5"
              >
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold">Current Snapshot</h3>
                  <span className="text-[10px] text-muted-foreground font-mono">
                    {state.selectedScan.scan_id}
                  </span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div>
                    <p className="text-muted-foreground">Domain</p>
                    <p className="font-medium font-mono mt-0.5">{state.selectedScan.domain}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Scan Time</p>
                    <p className="font-medium mt-0.5">
                      {new Date(state.selectedScan.timestamp).toLocaleString()}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Total Assets</p>
                    <p className="font-medium mt-0.5">{state.selectedScan.total_assets}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Exposure</p>
                    <p className={cn(
                      "font-semibold mt-0.5",
                      state.selectedScan.exposure_score > 60 ? "text-destructive" : "text-success"
                    )}>
                      {state.selectedScan.exposure_score}
                    </p>
                  </div>
                </div>
              </motion.div>
            )}
          </div>

          {/* Right sidebar */}
          <div className="space-y-4">
            <div className="rounded-xl border border-border bg-card p-4">
              <Bookmarks />
            </div>
            <div className="rounded-xl border border-border bg-card p-4">
              <ReplayFilters />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ReplayPage() {
  return (
    <ProtectedRoute>
      <ReplayProvider>
        <ReplayContent />
      </ReplayProvider>
    </ProtectedRoute>
  );
}
