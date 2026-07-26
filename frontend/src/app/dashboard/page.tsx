"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import {
  Globe,
  Loader2,
  AlertTriangle,
  ShieldAlert,
  Plus,
  ArrowRight,
  FileText,
  LayoutGrid,
  CheckCircle2,
  XCircle,
  Clock,
  Activity,
  Zap,
  ScanSearch,
  Radar,
  Sparkles,
  ScanLine,
} from "lucide-react";
import { motion } from "framer-motion";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { formatDistanceToNow, format } from "date-fns";
import { useAuth } from "@/contexts/AuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { listScans, createScan, getDashboardStats, getRecentActivity } from "@/lib/api";
import type { Scan } from "@/types";
import { getRiskLabel } from "@/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/common/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { StatCard } from "@/components/common/StatCard";
import { SeverityPill } from "@/components/common/SeverityPill";
import { GettingStartedChecklist } from "@/components/onboarding/GettingStartedChecklist";
import { StatusDot } from "@/components/common/StatusDot";
import { SkeletonBlock, SkeletonStat } from "@/components/common/SkeletonBlock";
import { EmptyState } from "@/components/common/EmptyState";
import { MetricSparkline } from "@/components/common/MetricSparkline";
import { TrendBadge } from "@/components/common/TrendBadge";

const CHART_COLORS = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-5))",
];

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

function ThreatScoreRing({ score }: { score: number }) {
  const radius = 64;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color =
    score <= 25 ? "hsl(var(--success))" : score <= 50 ? "hsl(var(--warning))" : score <= 75 ? "hsl(var(--warning))" : "hsl(var(--destructive))";

  return (
    <div className="relative flex items-center justify-center">
      <svg width="168" height="168" className="-rotate-90">
        <circle cx="84" cy="84" r={radius} fill="none" stroke="hsl(var(--border) / 0.3)" strokeWidth="10" />
        <circle
          cx="84"
          cy="84"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="score-circle"
          style={{ filter: `drop-shadow(0 0 8px ${color})` }}
        />
        <defs>
          <linearGradient id="scoreGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="hsl(var(--brand))" />
            <stop offset="100%" stopColor="hsl(var(--brand-2))" />
          </linearGradient>
        </defs>
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-5xl font-bold tracking-tight tabular-nums font-mono">{score}</span>
        <span className="text-xs text-muted-foreground/60 mt-1 font-mono">/ 100</span>
      </div>
    </div>
  );
}

function RiskTrendChart({ scans }: { scans: Scan[] }) {
  const chartData = useMemo(() => {
    const days = 30;
    const data: { date: string; score: number | null }[] = [];
    const now = new Date();
    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(now);
      d.setDate(d.getDate() - i);
      const label = format(d, "MMM dd");
      const matching = scans.filter((s) => {
        const created = new Date(s.created_at);
        return (
          created.getFullYear() === d.getFullYear() &&
          created.getMonth() === d.getMonth() &&
          created.getDate() === d.getDate()
        );
      });
      if (matching.length > 0) {
        const avgScore = Math.round(
          matching.reduce((acc, s) => acc + ((s as any).risk_score || 50), 0) / matching.length
        );
        data.push({ date: label, score: Math.max(0, Math.min(100, avgScore)) });
      } else {
        data.push({ date: label, score: null });
      }
    }
    return data;
  }, [scans]);

  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={chartData} margin={{ top: 5, right: 10, left: -15, bottom: 0 }}>
        <defs>
          <linearGradient id="colorScore" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="hsl(var(--brand))" stopOpacity={0.25} />
            <stop offset="95%" stopColor="hsl(var(--brand))" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border) / 0.4)" vertical={false} />
        <XAxis dataKey="date" tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 10, fontFamily: "var(--font-mono)" }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
        <YAxis tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 10, fontFamily: "var(--font-mono)" }} tickLine={false} axisLine={false} domain={[0, 100]} />
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
            fontSize: "11px",
            fontFamily: "var(--font-mono)",
            boxShadow: "0 4px 20px -4px hsl(0 0% 0% / 0.4)",
          }}
        />
        <Area type="monotone" dataKey="score" stroke="hsl(var(--brand))" strokeWidth={2} fill="url(#colorScore)" connectNulls={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function AssetDistributionChart({
  stats,
}: {
  stats: typeof EMPTY_STATS;
}) {
  const data = useMemo(
    () => [
      { name: "Subdomains", value: stats.subdomains || 0 },
      { name: "Ports", value: stats.ports || 0 },
      { name: "Certificates", value: stats.ssl_certificates || 0 },
      { name: "Technologies", value: stats.technologies || 0 },
    ],
    [stats]
  );
  const total = data.reduce((acc, d) => acc + d.value, 0);

  return (
    <div className="relative">
      <ResponsiveContainer width="100%" height={260}>
        <PieChart>
          <Pie data={data} cx="50%" cy="50%" innerRadius={65} outerRadius={95} paddingAngle={4} dataKey="value" stroke="none">
            {data.map((_, index) => (
              <Cell key={index} fill={CHART_COLORS[index]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "8px",
              fontSize: "11px",
              fontFamily: "var(--font-mono)",
              boxShadow: "0 4px 20px -4px hsl(0 0% 0% / 0.4)",
            }}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
        <span className="text-3xl font-bold tabular-nums font-mono">{total}</span>
        <span className="text-xs text-muted-foreground/60 font-mono">Total Assets</span>
      </div>
    </div>
  );
}

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
    <form onSubmit={handleSubmit} className="flex gap-2">
      <div className="relative flex-1">
        <ScanSearch className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          placeholder="example.com"
          className="h-10 pl-9 bg-surface-2/50"
          disabled={loading}
        />
      </div>
      <Button type="submit" disabled={loading || !domain.trim()} className="gradient-brand text-void shadow-glow-sm font-mono text-xs font-semibold">
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Radar className="h-4 w-4" />}
        Launch
      </Button>
    </form>
  );
}

function statusBadge(status: Scan["status"]) {
  switch (status) {
    case "completed":
      return (
        <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-phosphor font-mono">
          <StatusDot tone="success" /> Completed
        </span>
      );
    case "running":
      return (
        <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-cyan-signal font-mono">
          <StatusDot tone="active" pulse /> Running
        </span>
      );
    case "failed":
      return (
        <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-signal-red font-mono">
          <StatusDot tone="danger" /> Failed
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground font-mono">
          <StatusDot tone="muted" /> Pending
        </span>
      );
  }
}

function RecentScansTable({ scans, loading }: { scans: Scan[]; loading: boolean }) {
  const router = useRouter();

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3, 4, 5].map((i) => (
          <SkeletonBlock key={i} className="h-14" />
        ))}
      </div>
    );
  }

  if (scans.length === 0) {
    return (
      <EmptyState
        icon={<ScanSearch className="h-6 w-6" />}
        title="Nothing here yet"
        description="Point CAZO at a domain — results show up here as they resolve."
        action={
          <Link href="/scan/new">
            <Button size="sm" className="gradient-brand text-void font-mono text-xs font-semibold">
              RUN FIRST SCAN
            </Button>
          </Link>
        }
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-border/60">
            <th className="pb-3 text-left text-[10px] font-semibold uppercase tracking-[0.15em] text-muted-foreground/60 font-mono">Domain</th>
            <th className="pb-3 text-left text-[10px] font-semibold uppercase tracking-[0.15em] text-muted-foreground/60 font-mono">Status</th>
            <th className="pb-3 text-left text-[10px] font-semibold uppercase tracking-[0.15em] text-muted-foreground/60 font-mono">Risk</th>
            <th className="pb-3 text-right text-[10px] font-semibold uppercase tracking-[0.15em] text-muted-foreground/60 font-mono">Date</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border/40">
          {scans.slice(0, 6).map((scan) => {
            const score = (scan as any).risk_score ?? 42;
            const label = getRiskLabel(score);
            return (
              <tr
                key={scan.id}
                onClick={() => router.push(`/scan/${scan.id}`)}
                className="group cursor-pointer transition-colors hover:bg-surface-2/60"
              >
                <td className="py-3.5 pr-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-phosphor/8 text-phosphor">
                      <Globe className="h-4 w-4" />
                    </div>
                    <span className="font-medium text-sm group-hover:text-phosphor transition-colors font-mono">{scan.domain}</span>
                  </div>
                </td>
                <td className="py-3.5 pr-4">{statusBadge(scan.status)}</td>
                <td className="py-3.5 pr-4">
                  <span className="inline-flex items-center gap-1.5 text-sm font-semibold tabular-nums font-mono">
                    {score}
                    <span className="text-[10px] font-normal text-muted-foreground/60">{label}</span>
                  </span>
                </td>
                <td className="py-3.5 text-right">
                  <span className="text-xs text-muted-foreground">
                    {formatDistanceToNow(new Date(scan.created_at), { addSuffix: true })}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function DashboardContent() {
  const { user } = useAuth();
  const router = useRouter();
  const [scans, setScans] = useState<Scan[]>([]);
  const [loading, setLoading] = useState(true);
  const [dashStats, setDashStats] = useState(EMPTY_STATS);
  const [activity, setActivity] = useState<any[]>([]);

  useEffect(() => {
    Promise.all([
      listScans({ limit: 30 }).catch(() => []),
      getDashboardStats().catch(() => EMPTY_STATS),
      getRecentActivity(8).catch(() => []),
    ]).then(([scansData, stats, act]) => {
      setScans(scansData);
      setDashStats(stats);
      setActivity(act);
    }).finally(() => setLoading(false));
  }, []);

  const overallScore = useMemo(() => {
    const scansWithRisk = scans.filter((s) => s.status === "completed");
    if (scansWithRisk.length === 0) return 42;
    const totalRisk = scansWithRisk.reduce((acc, s) => acc + ((s as any).risk_score || 50), 0);
    return Math.round(totalRisk / scansWithRisk.length);
  }, [scans]);

  const firstName = user?.full_name?.split(" ")[0] || "there";
  const now = new Date();
  const exposureSpark = useMemo(
    () => scans.slice(-14).map((s) => (s as any).risk_score ?? 42),
    [scans]
  );

  const stats = [
    {
      label: "Total Assets",
      value: dashStats.subdomains,
      icon: Globe,
      accent: "brand" as const,
      hint: `${dashStats.ports} open ports`,
    },
    {
      label: "Active Scans",
      value: dashStats.running,
      icon: Loader2,
      accent: "info" as const,
      hint: dashStats.running > 0 ? "in progress" : "idle",
    },
    {
      label: "Vulnerabilities",
      value: dashStats.vulnerabilities,
      icon: AlertTriangle,
      accent: "warning" as const,
      hint: `${dashStats.completed} scans done`,
    },
    {
      label: "Failed Scans",
      value: dashStats.failed,
      icon: ShieldAlert,
      accent: "danger" as const,
      hint: dashStats.failed > 0 ? "needs attention" : "all clear",
    },
  ];

  return (
    <div className="page-container-lg">
      <div className="py-6 space-y-6">
      <PageHeader
        title={
          <span>
            Welcome back, <span className="gradient-text">{firstName}</span>
          </span>
        }
        description={`${format(now, "EEEE, MMMM d")} · Surface status as of ${format(now, "h:mm a")}`}
        icon={<Radar className="h-5 w-5" />}
        breadcrumbs={[{ label: "Home" }, { label: "Dashboard" }]}
        actions={
          <Link href="/scan/new">
            <Button className="gradient-brand text-void shadow-glow-sm font-mono text-xs font-semibold">
              <Plus className="h-4 w-4" /> New Scan
            </Button>
          </Link>
        }
      />

      {/* Getting Started Checklist */}
      <GettingStartedChecklist />

      {/* Hero: Threat Exposure Score */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}>
        <SectionCard accent="brand" className="overflow-hidden">
          <div className="flex flex-col items-center gap-8 md:flex-row md:items-center">
            <div className="flex-shrink-0">
              <ThreatScoreRing score={overallScore} />
            </div>
            <div className="flex-1 text-center md:text-left">
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.15em] text-muted-foreground/60 font-mono">
                Threat Exposure Score
              </p>
              <h2 className="text-3xl font-bold font-display">
                {getRiskLabel(overallScore)} <span className="text-muted-foreground">Risk</span>
              </h2>
              <p className="mt-2 max-w-md text-sm text-muted-foreground">
                Posture is assessed from subdomain exposure, open ports, SSL health, and
                discovered technology stacks across your attack surface.
              </p>
              <div className="mt-4 flex items-center justify-center gap-2 md:justify-start">
                {overallScore <= 50 ? (
                  <TrendBadge value={-12} />
                ) : (
                  <TrendBadge value={8} />
                )}
                <span className="text-xs text-muted-foreground">vs. previous baseline</span>
              </div>
            </div>
            <div className="grid w-full max-w-xs grid-cols-2 gap-3">
              {[
                { label: "Subdomains", value: dashStats.subdomains },
                { label: "Open Ports", value: dashStats.ports },
                { label: "Vulns", value: dashStats.vulnerabilities },
                { label: "Scans", value: dashStats.scans },
              ].map((item) => (
                <div key={item.label} className="rounded-xl border border-border/40 bg-surface-2/30 p-3">
                  <p className="text-2xl font-bold tabular-nums font-mono">{item.value}</p>
                  <p className="text-[10px] text-muted-foreground/60 font-mono uppercase tracking-wider">{item.label}</p>
                </div>
              ))}
            </div>
          </div>
        </SectionCard>
      </motion.div>

      {/* Stats Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {loading
          ? Array.from({ length: 4 }).map((_, i) => <SkeletonStat key={i} />)
          : stats.map((stat, i) => {
              const Icon = stat.icon;
              return (
                <motion.div key={stat.label} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: i * 0.08 }}>
                  <StatCard
                    label={stat.label}
                    value={<span className="tabular-nums">{stat.value}</span>}
                    icon={<Icon className="h-5 w-5" />}
                    accent={stat.accent}
                    hint={stat.hint}
                  />
                </motion.div>
              );
            })}
      </div>

      {/* Charts */}
      <div className="grid gap-6 lg:grid-cols-2">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.1 }}>
          <SectionCard
            title="Risk Trend"
            description="30-day exposure trend"
            icon={<Activity className="h-4 w-4" />}
          >
            {loading ? <SkeletonBlock className="h-[260px]" /> : <RiskTrendChart scans={scans} />}
          </SectionCard>
        </motion.div>
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.15 }}>
          <SectionCard
            title="Asset Distribution"
            description="Surface coverage"
            icon={<LayoutGrid className="h-4 w-4" />}
          >
            {loading ? (
              <SkeletonBlock className="h-[260px]" />
            ) : (
              <>
                <AssetDistributionChart stats={dashStats} />
                <div className="mt-2 flex items-center justify-center gap-5">
                  {[
                    { name: "Subdomains", color: CHART_COLORS[0] },
                    { name: "Ports", color: CHART_COLORS[1] },
                    { name: "Certificates", color: CHART_COLORS[2] },
                    { name: "Tech", color: CHART_COLORS[3] },
                  ].map((item) => (
                    <div key={item.name} className="flex items-center gap-2 text-xs">
                      <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                      <span className="text-muted-foreground">{item.name}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </SectionCard>
        </motion.div>
      </div>

      {/* Activity + Quick Actions */}
      <div className="grid gap-6 lg:grid-cols-3">
        <motion.div className="lg:col-span-2" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.2 }}>
          <SectionCard
            title="Recent Activity"
            icon={<Activity className="h-4 w-4" />}
            actions={
              <Link href="/scans">
                <Button variant="ghost" size="sm" className="h-8 gap-1 text-xs">
                  View All <ArrowRight className="h-3 w-3" />
                </Button>
              </Link>
            }
          >
            {activity.length === 0 ? (
              <EmptyState
                icon={<Activity className="h-6 w-6" />}
                title="No recent activity"
                description="Scan results stream in here."
                action={
                  <Link href="/scan/new">
                    <Button size="sm" className="gradient-brand text-void font-mono text-xs font-semibold">
                      RUN FIRST SCAN
                    </Button>
                  </Link>
                }
              />
            ) : (
              <div className="space-y-1">
                {activity.map((event, i) => {
                  const map: Record<string, { icon: any; tone: any }> = {
                    scan_completed: { icon: CheckCircle2, tone: "success" as const },
                    scan_started: { icon: Activity, tone: "active" as const },
                    scan_failed: { icon: AlertTriangle, tone: "danger" as const },
                  };
                  const cfg = map[event.type] || map.scan_completed;
                  const Icon = cfg.icon;
                  return (
                    <div
                      key={i}
                      onClick={() => event.scan_id && router.push(`/scan/${event.scan_id}`)}
                      className="flex cursor-pointer items-start gap-3 rounded-lg p-3 transition-colors hover:bg-surface-2/60"
                    >
                      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-surface-2/80">
                        <Icon className="h-4 w-4 text-phosphor" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm leading-tight">{event.description}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground">{event.time}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </SectionCard>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.25 }}>
          <SectionCard
            title="Quick Actions"
            icon={<Zap className="h-4 w-4" />}
            accent="violet"
          >
            <div className="space-y-3">
              <Link href="/scan/new" className="block">
                <Button className="h-12 w-full justify-start gap-3 gradient-brand text-void shadow-glow-sm">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-void/20">
                    <Zap className="h-4 w-4" />
                  </div>
                  <div className="text-left">
                    <p className="text-sm font-medium">New Scan</p>
                    <p className="text-xs text-white/70">Map attack surface</p>
                  </div>
                </Button>
              </Link>
              <Link href="/scans" className="block">
                <Button variant="outline" className="h-12 w-full justify-start gap-3 border-border/60 hover:bg-surface-2/60">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-success/10">
                    <LayoutGrid className="h-4 w-4 text-success" />
                  </div>
                  <div className="text-left">
                    <p className="text-sm font-medium">View Assets</p>
                    <p className="text-xs text-muted-foreground">Browse discovered assets</p>
                  </div>
                </Button>
              </Link>
              <Link href="/reports" className="block">
                <Button variant="outline" className="h-12 w-full justify-start gap-3 border-border/60 hover:bg-surface-2/60">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-2/10">
                    <FileText className="h-4 w-4 text-accent-2" />
                  </div>
                  <div className="text-left">
                    <p className="text-sm font-medium">Generate Report</p>
                    <p className="text-xs text-muted-foreground">Export security report</p>
                  </div>
                </Button>
              </Link>
              <div className="border-t border-border/40 pt-3">
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.15em] text-muted-foreground/60 font-mono">
                  Quick Scan
                </p>
                <QuickScanForm />
              </div>
            </div>
          </SectionCard>
        </motion.div>
      </div>

      {/* Recent Scans */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.3 }}>
        <SectionCard
          title="Recent Scans"
          description="Recent scans"
          icon={<ScanLine className="h-4 w-4" />}
          actions={
            scans.length > 0 ? (
              <Link href="/scans">
                <Button variant="ghost" size="sm" className="h-8 gap-1 text-xs">
                  View All <ArrowRight className="h-3 w-3" />
                </Button>
              </Link>
            ) : undefined
          }
        >
          <RecentScansTable scans={scans} loading={loading} />
        </SectionCard>
      </motion.div>
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
