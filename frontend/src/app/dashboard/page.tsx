"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Globe,
  Server,
  ShieldAlert,
  Lock,
  ScanSearch,
  Radar,
  Plus,
  ArrowRight,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  Activity,
  FileText,
  Layers,
} from "lucide-react";
import { formatDistanceToNow, format } from "date-fns";
import { useAuth } from "@/contexts/AuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import {
  listScans,
  createScan,
  getDashboardStats,
  getRecentActivity,
  getVulnerabilitySummary,
  listVulnerabilities,
} from "@/lib/api";
import type { Scan, Vulnerability } from "@/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/common/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { StatCard } from "@/components/common/StatCard";
import { SeverityPill } from "@/components/common/SeverityPill";
import { GettingStartedChecklist } from "@/components/onboarding/GettingStartedChecklist";
import { StatusDot } from "@/components/common/StatusDot";
import { SkeletonBlock, SkeletonStat } from "@/components/common/SkeletonBlock";
import { EmptyState } from "@/components/common/EmptyState";

/*
 * Dashboard — every number on this page comes from the API. Nothing is
 * estimated or defaulted to look busy: when there is no data the page says so.
 */

const EMPTY_STATS = {
  scans: 0,
  subdomains: 0,
  ports: 0,
  vulnerabilities: 0,
  running: 0,
  completed: 0,
  failed: 0,
  ssl_certificates: 0,
  technologies: 0,
  dns_records: 0,
};

type SeverityKey = "critical" | "high" | "medium" | "low";
const SEVERITIES: { key: SeverityKey; label: string; bar: string }[] = [
  { key: "critical", label: "Critical", bar: "bg-severity-critical" },
  { key: "high", label: "High", bar: "bg-severity-high" },
  { key: "medium", label: "Medium", bar: "bg-severity-medium" },
  { key: "low", label: "Low", bar: "bg-severity-low" },
];
const SEV_RANK: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4, unknown: 5 };

function fmt(n: number | undefined) {
  return (n ?? 0).toLocaleString();
}

/* ── Findings by severity ─────────────────────────────────────────── */

function SeverityBreakdown({
  summary,
  hosts,
}: {
  summary: Record<SeverityKey | "total", number>;
  hosts: { host: string; count: number; worst: string }[];
}) {
  const total = summary.total || 0;
  if (total === 0) {
    return (
      <EmptyState
        icon={<CheckCircle2 className="h-5 w-5" />}
        title="No open findings"
        description="Findings appear here once a scan completes."
        className="py-8"
      />
    );
  }
  return (
    <div>
      <div className="flex items-baseline gap-2">
        <span className="text-3xl font-semibold tracking-tight tabular-nums">{fmt(total)}</span>
        <span className="text-sm text-muted-foreground">open findings</span>
      </div>
      {/* Stacked bar */}
      <div className="mt-4 flex h-2.5 w-full overflow-hidden rounded-full bg-muted" role="img" aria-label="Findings by severity">
        {SEVERITIES.map((s) => {
          const v = summary[s.key] || 0;
          if (!v) return null;
          return <div key={s.key} className={cn("h-full", s.bar)} style={{ width: `${(v / total) * 100}%` }} />;
        })}
      </div>
      <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
        {SEVERITIES.map((s) => (
          <Link
            key={s.key}
            href={`/vulnerabilities?severity=${s.key}`}
            className="group rounded-md -m-1.5 p-1.5 transition-colors hover:bg-muted/60"
          >
            <dt className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className={cn("h-2 w-2 rounded-sm", s.bar)} aria-hidden="true" />
              {s.label}
            </dt>
            <dd className="mt-1 text-xl font-semibold tabular-nums">{fmt(summary[s.key])}</dd>
          </Link>
        ))}
      </dl>
      {hosts.length > 0 && (
        <div className="mt-6 border-t border-border pt-4">
          <p className="mb-2 text-xs font-medium text-muted-foreground">Most affected hosts</p>
          <ul className="space-y-1.5">
            {hosts.map((h) => (
              <li key={h.host} className="flex items-center gap-3 text-[13px]">
                <SeverityPill severity={h.worst} showDot={false} className="w-[64px] justify-center" />
                <span className="min-w-0 flex-1 truncate font-mono">{h.host}</span>
                <span className="shrink-0 tabular-nums text-muted-foreground">
                  {h.count} {h.count === 1 ? "finding" : "findings"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/* ── Inventory breakdown (horizontal bars, no donut) ──────────────── */

function InventoryBreakdown({ stats }: { stats: typeof EMPTY_STATS }) {
  const rows = [
    { label: "Hosts & subdomains", value: stats.subdomains, href: "/assets" },
    { label: "Open ports", value: stats.ports, href: "/assets?tab=ports" },
    { label: "DNS records", value: stats.dns_records, href: "/dns" },
    { label: "Technologies", value: stats.technologies, href: "/assets?tab=technologies" },
    { label: "TLS certificates", value: stats.ssl_certificates, href: "/assets?tab=ssl" },
  ];
  const max = Math.max(1, ...rows.map((r) => r.value || 0));
  return (
    <ul className="space-y-3.5">
      {rows.map((r) => (
        <li key={r.label}>
          <Link href={r.href} className="group block">
            <div className="flex items-center justify-between text-[13px]">
              <span className="text-muted-foreground transition-colors group-hover:text-foreground">{r.label}</span>
              <span className="font-medium tabular-nums">{fmt(r.value)}</span>
            </div>
            <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary/80" style={{ width: `${((r.value || 0) / max) * 100}%` }} />
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}

/* ── Top findings ─────────────────────────────────────────────────── */

function TopFindings({ findings, loading }: { findings: Vulnerability[]; loading: boolean }) {
  if (loading) {
    return (
      <div className="space-y-2 p-5">
        {[1, 2, 3, 4].map((i) => <SkeletonBlock key={i} className="h-10" />)}
      </div>
    );
  }
  if (findings.length === 0) {
    return (
      <div className="p-5">
        <EmptyState
          icon={<ShieldAlert className="h-5 w-5" />}
          title="Nothing to triage"
          description="When a scan finds an exposure it lands here, highest severity first."
          className="py-8"
        />
      </div>
    );
  }
  return (
    <ul className="divide-y divide-border">
      {findings.map((f) => (
        <li key={f.id}>
          <Link
            href={`/scan/${f.scan_id}?tab=findings`}
            className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-muted/50"
          >
            <SeverityPill severity={f.severity} className="w-[78px] justify-start" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-medium">{f.name}</p>
              <p className="truncate font-mono text-xs text-muted-foreground">{f.host}</p>
            </div>
            <span className="hidden shrink-0 text-xs text-muted-foreground sm:block">
              {formatDistanceToNow(new Date(f.found_at), { addSuffix: true })}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

/* ── Recent scans ─────────────────────────────────────────────────── */

function ScanStatus({ status, progress }: { status: Scan["status"]; progress: number }) {
  const map = {
    completed: { tone: "success" as const, label: "Completed", cls: "text-success" },
    running: { tone: "active" as const, label: `Running · ${progress ?? 0}%`, cls: "text-primary" },
    failed: { tone: "danger" as const, label: "Failed", cls: "text-destructive" },
    pending: { tone: "muted" as const, label: "Queued", cls: "text-muted-foreground" },
  };
  const s = map[status] ?? map.pending;
  return (
    <span className={cn("inline-flex items-center gap-2 text-xs font-medium", s.cls)}>
      <StatusDot tone={s.tone} pulse={status === "running"} />
      {s.label}
    </span>
  );
}

function duration(scan: Scan) {
  if (!scan.started_at || !scan.completed_at) return "—";
  const ms = new Date(scan.completed_at).getTime() - new Date(scan.started_at).getTime();
  if (ms < 0) return "—";
  const m = Math.floor(ms / 60000);
  const s = Math.round((ms % 60000) / 1000);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function RecentScansTable({ scans, loading }: { scans: Scan[]; loading: boolean }) {
  const router = useRouter();

  if (loading) {
    return (
      <div className="space-y-2 p-5">
        {[1, 2, 3, 4].map((i) => <SkeletonBlock key={i} className="h-10" />)}
      </div>
    );
  }

  if (scans.length === 0) {
    return (
      <div className="p-5">
        <EmptyState
          icon={<ScanSearch className="h-5 w-5" />}
          title="No scans yet"
          description="Point CAZO at a domain you own. Results stream in as each stage finishes."
          action={
            <Link href="/scan/new">
              <Button size="sm"><Radar className="h-4 w-4" /> Run your first scan</Button>
            </Link>
          }
        />
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b border-border bg-muted/30 text-left text-xs text-muted-foreground">
            <th scope="col" className="px-5 py-2.5 font-medium">Target</th>
            <th scope="col" className="px-3 py-2.5 font-medium">Status</th>
            <th scope="col" className="hidden px-3 py-2.5 font-medium md:table-cell">Profile</th>
            <th scope="col" className="hidden px-3 py-2.5 font-medium md:table-cell">Duration</th>
            <th scope="col" className="px-5 py-2.5 text-right font-medium">Started</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {scans.slice(0, 6).map((scan) => (
            <tr
              key={scan.id}
              onClick={() => router.push(`/scan/${scan.id}`)}
              className="group cursor-pointer transition-colors hover:bg-muted/50"
            >
              <td className="px-5 py-3">
                <Link href={`/scan/${scan.id}`} className="font-mono font-medium group-hover:text-primary" onClick={(e) => e.stopPropagation()}>
                  {scan.domain}
                </Link>
              </td>
              <td className="px-3 py-3"><ScanStatus status={scan.status} progress={scan.progress} /></td>
              <td className="hidden px-3 py-3 capitalize text-muted-foreground md:table-cell">{scan.scan_type || "—"}</td>
              <td className="hidden px-3 py-3 tabular-nums text-muted-foreground md:table-cell">{duration(scan)}</td>
              <td className="px-5 py-3 text-right text-muted-foreground">
                {formatDistanceToNow(new Date(scan.created_at), { addSuffix: true })}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── Activity ─────────────────────────────────────────────────────── */

function ActivityFeed({ activity }: { activity: any[] }) {
  const router = useRouter();
  if (activity.length === 0) {
    return (
      <EmptyState
        icon={<Activity className="h-5 w-5" />}
        title="No recent activity"
        description="Scan starts, completions and failures show up here."
        className="py-8"
      />
    );
  }
  const map: Record<string, { icon: any; cls: string }> = {
    scan_completed: { icon: CheckCircle2, cls: "text-success" },
    scan_started: { icon: Activity, cls: "text-primary" },
    scan_failed: { icon: AlertTriangle, cls: "text-destructive" },
  };
  return (
    <ol className="relative space-y-4 before:absolute before:left-[11px] before:top-2 before:bottom-2 before:w-px before:bg-border">
      {activity.map((event, i) => {
        const cfg = map[event.type] || map.scan_completed;
        const Icon = cfg.icon;
        return (
          <li
            key={i}
            onClick={() => event.scan_id && router.push(`/scan/${event.scan_id}`)}
            className={cn("relative flex gap-3", event.scan_id && "cursor-pointer")}
          >
            <span className="relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border bg-card">
              <Icon className={cn("h-3.5 w-3.5", cfg.cls)} />
            </span>
            <div className="min-w-0 pt-0.5">
              <p className="text-[13px] leading-snug">{event.description}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">{event.time}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/* ── Quick scan ───────────────────────────────────────────────────── */

function QuickScanForm() {
  const router = useRouter();
  const [domain, setDomain] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = domain.trim().toLowerCase();
    if (!trimmed) return;
    setLoading(true);
    try {
      const scan = await createScan(trimmed);
      router.push(`/scan/${scan.id}`);
    } catch {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2 sm:flex-row">
      <label htmlFor="quick-scan-domain" className="sr-only">Domain to scan</label>
      <div className="relative flex-1">
        <Globe className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          id="quick-scan-domain"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          placeholder="example.com"
          className="h-9 pl-9 font-mono"
          disabled={loading}
          autoComplete="off"
          spellCheck={false}
        />
      </div>
      <Button type="submit" disabled={loading || !domain.trim()}>
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Radar className="h-4 w-4" />}
        Scan
      </Button>
    </form>
  );
}

/* ── Page ─────────────────────────────────────────────────────────── */

function DashboardContent() {
  const { user } = useAuth();
  const [scans, setScans] = useState<Scan[]>([]);
  const [loading, setLoading] = useState(true);
  const [dashStats, setDashStats] = useState(EMPTY_STATS);
  const [activity, setActivity] = useState<any[]>([]);
  const [summary, setSummary] = useState<Record<SeverityKey | "total", number>>({
    total: 0, critical: 0, high: 0, medium: 0, low: 0,
  });
  const [findings, setFindings] = useState<Vulnerability[]>([]);
  const [allFindings, setAllFindings] = useState<Vulnerability[]>([]);

  useEffect(() => {
    Promise.all([
      listScans({ limit: 30 }).catch(() => []),
      getDashboardStats().catch(() => EMPTY_STATS),
      getRecentActivity(6).catch(() => []),
      getVulnerabilitySummary().catch(() => null),
      listVulnerabilities().catch(() => []),
    ]).then(([scansData, stats, act, sum, vulns]) => {
      setScans(scansData);
      setDashStats({ ...EMPTY_STATS, ...stats });
      setActivity(act);
      if (sum) setSummary({ total: 0, critical: 0, high: 0, medium: 0, low: 0, ...sum });
      setAllFindings(vulns as Vulnerability[]);
      setFindings(
        [...(vulns as Vulnerability[])]
          .sort((a, b) => (SEV_RANK[a.severity] ?? 9) - (SEV_RANK[b.severity] ?? 9))
          .slice(0, 6)
      );
    }).finally(() => setLoading(false));
  }, []);

  const firstName = user?.full_name?.split(" ")[0];
  const now = new Date();
  const lastCompleted = useMemo(
    () => scans.find((s) => s.status === "completed" && s.completed_at),
    [scans]
  );

  const topHosts = useMemo(() => {
    const by = new Map<string, { host: string; count: number; worst: string }>();
    for (const f of allFindings) {
      const host = f.host || "unknown";
      const cur = by.get(host) ?? { host, count: 0, worst: "unknown" };
      cur.count += 1;
      if ((SEV_RANK[f.severity] ?? 9) < (SEV_RANK[cur.worst] ?? 9)) cur.worst = f.severity;
      by.set(host, cur);
    }
    return Array.from(by.values())
      .sort((a, b) => (SEV_RANK[a.worst] ?? 9) - (SEV_RANK[b.worst] ?? 9) || b.count - a.count)
      .slice(0, 3);
  }, [allFindings]);

  const kpis = [
    {
      label: "Hosts & subdomains",
      value: fmt(dashStats.subdomains),
      icon: Globe,
      accent: "brand" as const,
      hint: `${fmt(dashStats.dns_records)} DNS records`,
    },
    {
      label: "Open ports",
      value: fmt(dashStats.ports),
      icon: Server,
      accent: "info" as const,
      hint: `${fmt(dashStats.technologies)} technologies`,
    },
    {
      label: "Open findings",
      value: fmt(summary.total || dashStats.vulnerabilities),
      icon: ShieldAlert,
      accent: summary.critical > 0 ? ("danger" as const) : ("warning" as const),
      hint: summary.critical > 0 ? `${fmt(summary.critical)} critical` : "none critical",
    },
    {
      label: "TLS certificates",
      value: fmt(dashStats.ssl_certificates),
      icon: Lock,
      accent: "success" as const,
      hint: "tracked for expiry",
    },
  ];

  return (
    <div className="page-container-lg py-6">
      <PageHeader
        title={firstName ? `Welcome back, ${firstName}` : "Overview"}
        description={
          lastCompleted?.completed_at
            ? `Last scan finished ${formatDistanceToNow(new Date(lastCompleted.completed_at), { addSuffix: true })} · ${dashStats.running > 0 ? `${dashStats.running} running now` : "no scans running"}`
            : `${format(now, "EEEE, MMMM d")}`
        }
        actions={
          <>
            <Link href="/reports">
              <Button variant="outline"><FileText className="h-4 w-4" /> Reports</Button>
            </Link>
            <Link href="/scan/new">
              <Button><Plus className="h-4 w-4" /> New scan</Button>
            </Link>
          </>
        }
      />

      <div className="space-y-6">
        <GettingStartedChecklist />

        {/* KPI row */}
        <div className="grid grid-cols-2 gap-3 md:gap-4 xl:grid-cols-4">
          {loading
            ? Array.from({ length: 4 }).map((_, i) => <SkeletonStat key={i} />)
            : kpis.map((k) => {
                const Icon = k.icon;
                return (
                  <StatCard
                    key={k.label}
                    label={k.label}
                    value={k.value}
                    icon={<Icon />}
                    accent={k.accent}
                    hint={k.hint}
                  />
                );
              })}
        </div>

        {/* Severity + inventory */}
        <div className="grid gap-6 lg:grid-cols-5">
          <SectionCard
            title="Findings by severity"
            description="Across all assets in your organization"
            icon={<ShieldAlert />}
            className="lg:col-span-3"
            actions={
              <Link href="/vulnerabilities">
                <Button variant="ghost" size="sm" className="h-8 gap-1 text-xs">
                  All findings <ArrowRight className="h-3 w-3" />
                </Button>
              </Link>
            }
          >
            {loading ? <SkeletonBlock className="h-[132px]" /> : <SeverityBreakdown summary={summary} hosts={topHosts} />}
          </SectionCard>

          <SectionCard
            title="Inventory"
            description="What CAZO has discovered"
            icon={<Layers />}
            className="lg:col-span-2"
          >
            {loading ? <SkeletonBlock className="h-[200px]" /> : <InventoryBreakdown stats={dashStats} />}
          </SectionCard>
        </div>

        {/* Top findings + activity */}
        <div className="grid gap-6 lg:grid-cols-5">
          <SectionCard
            title="Top findings"
            description="Highest severity first"
            icon={<AlertTriangle />}
            className="lg:col-span-3"
            bodyClassName="p-0"
          >
            <TopFindings findings={findings} loading={loading} />
          </SectionCard>

          <SectionCard
            title="Activity"
            icon={<Activity />}
            className="lg:col-span-2"
          >
            {loading ? <SkeletonBlock className="h-[200px]" /> : <ActivityFeed activity={activity} />}
            <div className="mt-5 border-t border-border pt-4">
              <p className="mb-2 text-xs font-medium text-muted-foreground">Quick scan</p>
              <QuickScanForm />
            </div>
          </SectionCard>
        </div>

        {/* Recent scans */}
        <SectionCard
          title="Recent scans"
          icon={<ScanSearch />}
          bodyClassName="p-0"
          actions={
            scans.length > 0 ? (
              <Link href="/scans">
                <Button variant="ghost" size="sm" className="h-8 gap-1 text-xs">
                  View all <ArrowRight className="h-3 w-3" />
                </Button>
              </Link>
            ) : undefined
          }
        >
          <RecentScansTable scans={scans} loading={loading} />
        </SectionCard>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  );
}
