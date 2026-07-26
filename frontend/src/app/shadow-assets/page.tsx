"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Ghost,
  Loader2,
  ShieldCheck,
  ShieldX,
  Search,
  Eye,
  CheckCircle2,
  XCircle,
  Flag,
  ChevronRight,
  Clock,
  Settings,
} from "lucide-react";
import { PageHeader } from "@/components/common/PageHeader";
import { DocTooltip } from "@/components/common/DocTooltip";
import { StatCard } from "@/components/common/StatCard";
import { SectionCard } from "@/components/common/SectionCard";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { cn } from "@/lib/utils";
import {
  listShadowAssets,
  reviewShadowAsset,
  getShadowReviewLog,
  type ShadowCandidate,
  type ShadowSignal,
} from "@/lib/api";

function relativeTime(value: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  const diff = Date.now() - d.getTime();
  const day = Math.round(diff / (1000 * 60 * 60 * 24));
  if (day < 1) return "today";
  if (day < 30) return `${day}d ago`;
  return d.toLocaleDateString();
}

function confidenceColor(conf: number): string {
  if (conf >= 85) return "text-destructive";
  if (conf >= 70) return "text-warning";
  if (conf >= 40) return "text-amber";
  return "text-muted-foreground";
}

function confidenceBar(conf: number): string {
  if (conf >= 85) return "bg-destructive";
  if (conf >= 70) return "bg-warning";
  if (conf >= 40) return "bg-amber";
  return "bg-muted-foreground";
}

function signalLabel(sig: ShadowSignal): string {
  if (sig.type === "shared_ip") return "Shared IP";
  if (sig.type === "shared_cert") return "Shared Certificate";
  if (sig.type === "shared_asn")
    return sig.cloud ? "Shared ASN (cloud)" : "Shared ASN";
  return sig.type;
}

function signalVariant(sig: ShadowSignal): "destructive" | "warning" | "secondary" {
  if (sig.type === "shared_cert") return "destructive";
  if (sig.type === "shared_ip") return "warning";
  return "secondary";
}

function ShadowAssetsContent() {
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [shadows, setShadows] = useState<ShadowCandidate[]>([]);
  const [knownCount, setKnownCount] = useState(0);
  const [discoveredCount, setDiscoveredCount] = useState(0);
  const [filter, setFilter] = useState("all"); // all | high | medium | low
  const [search, setSearch] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [log, setLog] = useState<any[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await listShadowAssets();
      setShadows(data.shadows);
      setKnownCount(data.known_count);
      setDiscoveredCount(data.discovered_count);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || "Failed to load shadow assets.";
      setLoadError(detail);
    }
    try {
      const lg = await getShadowReviewLog();
      setLog(lg);
    } catch {
      // review log is non-critical; silently ignore failures
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleReview = async (
    assetId: string,
    action: "confirm" | "reject" | "investigate"
  ) => {
    setReviewError(null);
    setPending(assetId);
    try {
      await reviewShadowAsset(assetId, action);
      await load();
    } catch (err: any) {
      // Surface the failure inline instead of letting it bubble up as an
      // unhandled runtime error that whites out the whole page.
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        "Failed to apply review. Please try again.";
      setReviewError(`${action} failed: ${detail}`);
    } finally {
      setPending(null);
    }
  };

  const filtered = shadows.filter((s) => {
    if (search && !s.value.toLowerCase().includes(search.toLowerCase())) return false;
    if (filter === "high" && s.confidence < 85) return false;
    if (filter === "medium" && (s.confidence < 70 || s.confidence >= 85)) return false;
    if (filter === "low" && s.confidence >= 70) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Shadow Asset Detection"
        description="Hosts that share infrastructure (IP, TLS certificate, or ASN) with your confirmed inventory but were never confirmed as yours."
      />

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard
          label="Shadow Candidates"
          value={shadows.length}
          icon={<Ghost className="h-5 w-5" />}
          hint="Flagged by infra overlap"
        />
        <StatCard
          label="Confirmed Inventory"
          value={knownCount}
          icon={<ShieldCheck className="h-5 w-5" />}
          hint="Baseline for detection"
        />
        <StatCard
          label="Discovered (unconfirmed)"
          value={discoveredCount}
          icon={<Search className="h-5 w-5" />}
          hint="Auto-discovered via scans"
        />
      </div>

      {knownCount === 0 && (
        <div className="rounded-lg border border-warning/30 bg-warning/5 p-4 text-sm text-warning">
          <Flag className="mr-2 inline h-4 w-4" />
          No confirmed inventory yet. Confirm at least one asset as{" "}
          <span className="font-semibold">known</span> (e.g. your apex domain) so
          detection has a baseline to compare against. Until then, nothing is flagged.
        </div>
      )}

      {loadError && (
        <div className="rounded-lg border border-warning/30 bg-warning/5 p-4 text-sm text-warning">
          <Flag className="mr-2 inline h-4 w-4" />
          {loadError}
          {loadError.includes("organization") && (
            <a
              href="/settings/organization"
              className="ml-2 inline-flex items-center gap-1 font-semibold underline underline-offset-2 hover:text-warning/80"
            >
              <Settings className="h-3.5 w-3.5" /> Create Organization
            </a>
          )}
        </div>
      )}

      {reviewError && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          <XCircle className="mr-2 inline h-4 w-4" />
          {reviewError}
        </div>
      )}

      <SectionCard
        title={
          <span className="flex items-center gap-2">
            Possible Shadow Assets
            <DocTooltip article="shadow-assets" />
          </span>
        }
        actions={
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Filter hosts..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8 w-44"
              />
            </div>
            <div className="flex rounded-md border border-border overflow-hidden">
              {[
                ["all", "All"],
                ["high", "High"],
                ["medium", "Medium"],
                ["low", "Low"],
              ].map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setFilter(key)}
                  className={cn(
                    "px-3 py-1.5 text-xs font-medium transition-colors",
                    filter === key
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-secondary"
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        }
      >
        {loading ? (
          <div className="flex items-center justify-center py-12 text-muted-foreground">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading candidates...
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<Ghost className="h-8 w-8" />}
            title="No shadow assets yet"
            description="Shadow assets appear when we find infrastructure that's probably yours — shared certs, IPs, or ASNs you haven't confirmed yet."
          />
        ) : (
          <div className="divide-y divide-border">
            {filtered.map((s) => (
              <div
                key={s.asset_id}
                className="flex flex-col gap-3 py-4 md:flex-row md:items-center md:justify-between"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm text-foreground truncate">
                      {s.value}
                    </span>
                    {s.signals.map((sig, i) => (
                      <Badge key={i} variant={signalVariant(sig)}>
                        {signalLabel(sig)}
                      </Badge>
                    ))}
                  </div>
                  <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" /> first seen {relativeTime(s.first_seen)}
                    </span>
                    <span>
                      {s.signals.length} shared-infra signal
                      {s.signals.length !== 1 ? "s" : ""}
                    </span>
                  </div>
                  {/* Confidence bar */}
                  <div className="mt-2 flex items-center gap-2">
                    <div className="h-1.5 w-32 rounded-full bg-secondary">
                      <div
                        className={cn("h-1.5 rounded-full", confidenceBar(s.confidence))}
                        style={{ width: `${s.confidence}%` }}
                      />
                    </div>
                    <span className={cn("text-xs font-semibold", confidenceColor(s.confidence))}>
                      {s.confidence}% confidence
                    </span>
                  </div>
                </div>

                <div className="flex shrink-0 items-center gap-2">
                  <Button
                    size="sm"
                    variant="default"
                    disabled={pending === s.asset_id}
                    onClick={() => handleReview(s.asset_id, "confirm")}
                    className="bg-success hover:bg-success/90 text-success-foreground"
                  >
                    <CheckCircle2 className="mr-1 h-3.5 w-3.5" /> Confirm
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={pending === s.asset_id}
                    onClick={() => handleReview(s.asset_id, "investigate")}
                  >
                    <Eye className="mr-1 h-3.5 w-3.5" /> Investigate
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={pending === s.asset_id}
                    onClick={() => handleReview(s.asset_id, "reject")}
                    className="text-destructive hover:bg-destructive/10"
                  >
                    <XCircle className="mr-1 h-3.5 w-3.5" /> Reject
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      {log.length > 0 && (
        <SectionCard title="Review History">
          <div className="divide-y divide-border">
            {log.map((l) => (
              <div
                key={l.id}
                className="flex items-center justify-between py-2 text-sm"
              >
                <div className="flex items-center gap-2">
                  {l.action === "confirm" ? (
                    <CheckCircle2 className="h-4 w-4 text-success" />
                  ) : l.action === "reject" ? (
                    <XCircle className="h-4 w-4 text-destructive" />
                  ) : (
                    <Flag className="h-4 w-4 text-warning" />
                  )}
                  <span className="font-mono text-xs text-foreground">
                    {l.asset_id.slice(0, 8)}
                  </span>
                  <Badge variant="secondary" className="capitalize">
                    {l.action}
                  </Badge>
                  <span className="text-muted-foreground">
                    → {l.new_status}
                  </span>
                </div>
                <span className="text-xs text-muted-foreground">
                  {relativeTime(l.created_at)}
                </span>
              </div>
            ))}
          </div>
        </SectionCard>
      )}
    </div>
  );
}

export default function ShadowAssetsPage() {
  return (
    <ProtectedRoute>
      <ShadowAssetsContent />
    </ProtectedRoute>
  );
}
