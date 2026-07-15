"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import {
  Globe,
  Loader,
  AlertTriangle,
  Lock,
  Plus,
  ArrowRight,
  FileText,
  LayoutGrid,
  CheckCircle,
  XCircle,
  Clock,
  Activity,
  TrendingUp,
  TrendingDown,
  Zap,
  Search,
  ScanSearch,
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
  Legend,
} from "recharts";
import { formatDistanceToNow, format } from "date-fns";
import { useAuth } from "@/contexts/AuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { listScans, createScan, getDashboardStats, getRecentActivity } from "@/lib/api";
import type { Scan } from "@/types";
import { getRiskLabel } from "@/types";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useRouter } from "next/navigation";

function AnimatedCounter({ value, duration = 1000 }: { value: number; duration?: number }) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let start = 0;
    const end = value;
    if (start === end) return;
    const increment = end / (duration / 16);
    const timer = setInterval(() => {
      start += increment;
      if (start >= end) {
        setCount(end);
        clearInterval(timer);
      } else {
        setCount(Math.floor(start));
      }
    }, 16);
    return () => clearInterval(timer);
  }, [value, duration]);

  return <>{count}</>;
}

function ThreatScoreRing({ score }: { score: number }) {
  const radius = 70;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  const gradientId = "scoreGradient";
  const color =
    score <= 25 ? "#10b981" : score <= 50 ? "#f59e0b" : score <= 75 ? "#f97316" : "#ef4444";

  return (
    <div className="relative flex items-center justify-center">
      <svg width="180" height="180" className="-rotate-90">
        <circle
          cx="90"
          cy="90"
          r={radius}
          fill="none"
          stroke="hsl(var(--border))"
          strokeWidth="10"
        />
        <circle
          cx="90"
          cy="90"
          r={radius}
          fill="none"
          stroke={`url(#${gradientId})`}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-1500 ease-out"
        />
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={color} />
            <stop offset="100%" stopColor="hsl(187, 100%, 50%)" />
          </linearGradient>
        </defs>
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-5xl font-bold tracking-tight">{score}</span>
        <span className="text-xs text-muted-foreground mt-1">/ 100</span>
      </div>
    </div>
  );
}

function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton rounded-lg", className)} />;
}

function StatCardSkeleton() {
  return (
    <Card className="glass">
      <CardContent className="p-6">
        <div className="flex items-center justify-between mb-4">
          <Skeleton className="h-10 w-10 rounded-xl" />
          <Skeleton className="h-4 w-12" />
        </div>
        <Skeleton className="h-8 w-16 mb-2" />
        <Skeleton className="h-3 w-20" />
      </CardContent>
    </Card>
  );
}

const CHART_COLORS = ["#2563EB", "#00E5FF", "#10B981", "#F59E0B"];

function RiskTrendChart({ scans }: { scans: Scan[] }) {
  const chartData = useMemo(() => {
    const days = 30;
    const data = [];
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
            <stop offset="5%" stopColor="#2563EB" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#2563EB" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          domain={[0, 100]}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
            fontSize: "12px",
          }}
        />
        <Area
          type="monotone"
          dataKey="score"
          stroke="#2563EB"
          strokeWidth={2}
          fill="url(#colorScore)"
          connectNulls={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function AssetDistributionChart({ stats }: { stats: { subdomains: number; ports: number; ssl_certificates: number; technologies: number } }) {
  const data = useMemo(() => {
    return [
      { name: "Subdomains", value: stats.subdomains || 0 },
      { name: "Ports", value: stats.ports || 0 },
      { name: "Certificates", value: stats.ssl_certificates || 0 },
      { name: "Technologies", value: stats.technologies || 0 },
    ];
  }, [stats]);

  const total = data.reduce((acc, d) => acc + d.value, 0);

  return (
    <div className="relative">
      <ResponsiveContainer width="100%" height={260}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={65}
            outerRadius={95}
            paddingAngle={4}
            dataKey="value"
            stroke="none"
          >
            {data.map((_, index) => (
              <Cell key={index} fill={CHART_COLORS[index]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "8px",
              fontSize: "12px",
            }}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
        <span className="text-3xl font-bold">{total}</span>
        <span className="text-xs text-muted-foreground">Total Assets</span>
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
    <form onSubmit={handleSubmit} className="flex gap-3">
      <div className="relative flex-1">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="text"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          placeholder="Enter domain (e.g. example.com)"
          className="h-11 pl-10 bg-secondary/50 border-border/50"
          disabled={loading}
        />
      </div>
      <Button
        type="submit"
        disabled={loading || !domain.trim()}
        className="h-11 px-6 bg-gradient-to-r from-primary to-cyan-500 hover:from-primary/90 hover:to-cyan-500/90"
      >
        {loading ? (
          <Loader className="h-4 w-4 animate-spin" />
        ) : (
          <ScanSearch className="h-4 w-4" />
        )}
        Scan
      </Button>
    </form>
  );
}

function RecentScansTable({ scans, loading }: { scans: Scan[]; loading: boolean }) {
  const router = useRouter();

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-14 skeleton rounded-lg" />
        ))}
      </div>
    );
  }

  if (scans.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <div className="rounded-2xl bg-secondary/50 p-5 mb-4">
          <ScanSearch className="h-8 w-8 text-muted-foreground" />
        </div>
        <p className="text-sm font-medium text-foreground mb-1">No scans yet</p>
        <p className="text-xs text-muted-foreground mb-4">
          Run your first domain scan to see results here.
        </p>
        <Link href="/scan/new">
          <Button size="sm" className="bg-gradient-to-r from-primary to-cyan-500">
            <Plus className="h-3.5 w-3.5" />
            Start Scanning
          </Button>
        </Link>
      </div>
    );
  }

  function statusBadge(status: Scan["status"]) {
    switch (status) {
      case "completed":
        return (
          <Badge variant="outline" className="border-emerald-500/30 text-emerald-400 bg-emerald-500/10 gap-1">
            <CheckCircle className="h-3 w-3" />
            Completed
          </Badge>
        );
      case "running":
        return (
          <Badge variant="outline" className="border-blue-500/30 text-blue-400 bg-blue-500/10 gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse" />
            Running
          </Badge>
        );
      case "failed":
        return (
          <Badge variant="outline" className="border-red-500/30 text-red-400 bg-red-500/10 gap-1">
            <XCircle className="h-3 w-3" />
            Failed
          </Badge>
        );
      default:
        return (
          <Badge variant="outline" className="border-muted-foreground/30 text-muted-foreground gap-1">
            <Clock className="h-3 w-3" />
            Pending
          </Badge>
        );
    }
  }

  function riskBadge(scan: Scan) {
    const score = (scan as any).risk_score ?? 42;
    const label = getRiskLabel(score);
    const colorMap: Record<string, string> = {
      Low: "border-emerald-500/30 text-emerald-400 bg-emerald-500/10",
      Medium: "border-amber-500/30 text-amber-400 bg-amber-500/10",
      High: "border-orange-500/30 text-orange-400 bg-orange-500/10",
      Critical: "border-red-500/30 text-red-400 bg-red-500/10",
    };
    return (
      <Badge variant="outline" className={cn("gap-1", colorMap[label])}>
        {score}
      </Badge>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-border/50">
            <th className="pb-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Domain
            </th>
            <th className="pb-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Status
            </th>
            <th className="pb-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Risk
            </th>
            <th className="pb-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Date
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border/30">
          {scans.slice(0, 6).map((scan) => (
            <tr
              key={scan.id}
              onClick={() => router.push(`/scan/${scan.id}`)}
              className="group cursor-pointer transition-colors hover:bg-secondary/30"
            >
              <td className="py-3.5 pr-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <Globe className="h-4 w-4" />
                  </div>
                  <span className="font-medium text-sm group-hover:text-primary transition-colors">
                    {scan.domain}
                  </span>
                </div>
              </td>
              <td className="py-3.5 pr-4">{statusBadge(scan.status)}</td>
              <td className="py-3.5 pr-4">{riskBadge(scan)}</td>
              <td className="py-3.5 text-right">
                <span className="text-xs text-muted-foreground">
                  {formatDistanceToNow(new Date(scan.created_at), { addSuffix: true })}
                </span>
              </td>
            </tr>
          ))}
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
  const [dashStats, setDashStats] = useState({ scans: 0, subdomains: 0, ports: 0, vulnerabilities: 0, running: 0, completed: 0, failed: 0, ssl_certificates: 0, technologies: 0, dns_records: 0 });
  const [activity, setActivity] = useState<any[]>([]);

  useEffect(() => {
    Promise.all([
      listScans({ limit: 30 }).catch(() => []),
      getDashboardStats().catch(() => ({ scans: 0, subdomains: 0, ports: 0, vulnerabilities: 0, running: 0, completed: 0, failed: 0, ssl_certificates: 0, technologies: 0, dns_records: 0 })),
      getRecentActivity(8).catch(() => []),
    ]).then(([scansData, stats, act]) => {
      setScans(scansData);
      setDashStats(stats);
      setActivity(act);
    }).finally(() => setLoading(false));
  }, []);

  const completedScans = scans.filter((s) => s.status === "completed");
  const runningScans = scans.filter((s) => s.status === "running");
  const failedScans = scans.filter((s) => s.status === "failed");

  const overallScore = useMemo(() => {
    const scansWithRisk = scans.filter((s) => s.status === "completed");
    if (scansWithRisk.length === 0) return 42;
    const totalRisk = scansWithRisk.reduce((acc, s) => acc + ((s as any).risk_score || 50), 0);
    return Math.round(totalRisk / scansWithRisk.length);
  }, [scans]);

  const firstName = user?.full_name?.split(" ")[0] || "there";
  const now = new Date();

  const stats = [
    {
      label: "Total Assets",
      value: dashStats.subdomains,
      icon: Globe,
      color: "text-emerald-400",
      bg: "bg-emerald-500/10",
      trend: `${dashStats.ports} ports`,
      trendUp: true,
    },
    {
      label: "Active Scans",
      value: dashStats.running,
      icon: Loader,
      color: "text-blue-400",
      bg: "bg-blue-500/10",
      trend: dashStats.running > 0 ? "In progress" : "0",
      trendUp: true,
    },
    {
      label: "Vulnerabilities",
      value: dashStats.vulnerabilities,
      icon: AlertTriangle,
      color: "text-amber-400",
      bg: "bg-amber-500/10",
      trend: `${dashStats.completed} scans done`,
      trendUp: dashStats.vulnerabilities === 0,
    },
    {
      label: "Failed Scans",
      value: dashStats.failed,
      icon: Lock,
      color: "text-red-400",
      bg: "bg-red-500/10",
      trend: dashStats.failed > 0 ? "Needs attention" : "All clear",
      trendUp: dashStats.failed === 0,
    },
  ];

  return (
    <div className="min-h-screen page-transition">
      <div className="border-b bg-card/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="mx-auto max-w-7xl px-6 py-5">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold tracking-tight">
                Welcome back, <span className="gradient-text">{firstName}</span>
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                {format(now, "EEEE, MMMM d, yyyy")} &middot; Last updated just now
              </p>
            </div>
            <Link href="/scan/new">
              <Button className="bg-gradient-to-r from-primary to-cyan-500 hover:from-primary/90 hover:to-cyan-500/90 shadow-lg shadow-primary/20">
                <Plus className="h-4 w-4" />
                New Scan
              </Button>
            </Link>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-6 py-8 space-y-8">
        {/* Hero: Threat Score */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <Card className="glass gradient-border overflow-hidden">
            <CardContent className="p-8">
              <div className="flex flex-col md:flex-row items-center gap-8">
                <div className="flex-shrink-0">
                  <ThreatScoreRing score={overallScore} />
                </div>
                <div className="flex-1 text-center md:text-left">
                  <p className="text-sm text-muted-foreground uppercase tracking-widest mb-2">
                    Threat Exposure Score
                  </p>
                  <h2 className="text-3xl font-bold mb-2">
                    {getRiskLabel(overallScore)} Risk
                  </h2>
                  <p className="text-muted-foreground text-sm max-w-md">
                    Your overall security posture is assessed based on subdomain exposure,
                    open ports, SSL health, and discovered technologies.
                  </p>
                  <div className="flex items-center gap-2 mt-4 justify-center md:justify-start">
                    {overallScore <= 50 ? (
                      <TrendingDown className="h-4 w-4 text-emerald-400" />
                    ) : (
                      <TrendingUp className="h-4 w-4 text-red-400" />
                    )}
                    <span className={cn(
                      "text-sm font-medium",
                      overallScore <= 50 ? "text-emerald-400" : "text-red-400"
                    )}>
                      {overallScore <= 50 ? "Improving" : "Needs attention"}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      from last scan
                    </span>
                  </div>
                </div>
                <div className="hidden lg:flex flex-col gap-2">
                  {[
                    { label: "Subdomains", value: dashStats.subdomains, color: "bg-blue-500" },
                    { label: "Open Ports", value: dashStats.ports, color: "bg-cyan-500" },
                    { label: "Vulnerabilities", value: dashStats.vulnerabilities, color: "bg-emerald-500" },
                    { label: "Total Scans", value: dashStats.scans, color: "bg-amber-500" },
                  ].map((item) => (
                    <div key={item.label} className="flex items-center gap-3 text-sm">
                      <div className={cn("h-2 w-2 rounded-full", item.color)} />
                      <span className="text-muted-foreground w-24">{item.label}</span>
                      <span className="font-semibold">{item.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Stats Grid */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {loading ? (
            <>
              <StatCardSkeleton />
              <StatCardSkeleton />
              <StatCardSkeleton />
              <StatCardSkeleton />
            </>
          ) : (
            stats.map((stat, i) => {
              const Icon = stat.icon;
              return (
                <motion.div
                  key={stat.label}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, delay: i * 0.1 }}
                >
                  <Card className="glass hover-glow group cursor-default">
                    <CardContent className="p-6">
                      <div className="flex items-center justify-between mb-4">
                        <div className={cn("flex h-10 w-10 items-center justify-center rounded-xl", stat.bg)}>
                          <Icon className={cn("h-5 w-5", stat.color)} />
                        </div>
                        <div className="flex items-center gap-1 text-xs">
                          {stat.trendUp ? (
                            <TrendingUp className="h-3 w-3 text-emerald-400" />
                          ) : (
                            <TrendingDown className="h-3 w-3 text-red-400" />
                          )}
                          <span className={stat.trendUp ? "text-emerald-400" : "text-red-400"}>
                            {stat.trend}
                          </span>
                        </div>
                      </div>
                      <div className="text-3xl font-bold mb-1">
                        <AnimatedCounter value={stat.value} />
                      </div>
                      <p className="text-xs text-muted-foreground">{stat.label}</p>
                    </CardContent>
                  </Card>
                </motion.div>
              );
            })
          )}
        </div>

        {/* Charts Section */}
        <div className="grid gap-6 lg:grid-cols-2">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            <Card className="glass">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-medium">Risk Trend</CardTitle>
                  <span className="text-xs text-muted-foreground">Last 30 days</span>
                </div>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="h-[260px] skeleton rounded-lg" />
                ) : (
                  <RiskTrendChart scans={scans} />
                )}
              </CardContent>
            </Card>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
          >
            <Card className="glass">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-medium">Asset Distribution</CardTitle>
                  <span className="text-xs text-muted-foreground">All scans</span>
                </div>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="h-[260px] skeleton rounded-lg" />
                ) : (
                  <>
                    <AssetDistributionChart stats={dashStats} />
                    <div className="flex items-center justify-center gap-5 mt-2">
                      {[
                        { name: "Subdomains", color: CHART_COLORS[0] },
                        { name: "Ports", color: CHART_COLORS[1] },
                        { name: "Certificates", color: CHART_COLORS[2] },
                        { name: "Technologies", color: CHART_COLORS[3] },
                      ].map((item) => (
                        <div key={item.name} className="flex items-center gap-2 text-xs">
                          <div
                            className="h-2.5 w-2.5 rounded-full"
                            style={{ backgroundColor: item.color }}
                          />
                          <span className="text-muted-foreground">{item.name}</span>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* Bottom Row: Activity + Quick Actions */}
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Activity Feed */}
          <motion.div
            className="lg:col-span-2"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.4 }}
          >
            <Card className="glass">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-medium">Recent Activity</CardTitle>
                  <Link href="/scans">
                    <Button variant="ghost" size="sm" className="text-xs gap-1 h-8">
                      View All
                      <ArrowRight className="h-3 w-3" />
                    </Button>
                  </Link>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-1">
                  {activity.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-8 text-center">
                      <Activity className="h-8 w-8 text-muted-foreground mb-2" />
                      <p className="text-sm text-muted-foreground">No recent activity</p>
                    </div>
                  ) : (
                    activity.map((event, i) => {
                      const typeConfig: Record<string, { icon: any; color: string; bg: string }> = {
                        scan_completed: { icon: CheckCircle, color: "text-emerald-500", bg: "bg-emerald-500/10" },
                        scan_started: { icon: Activity, color: "text-blue-500", bg: "bg-blue-500/10" },
                        scan_failed: { icon: AlertTriangle, color: "text-red-500", bg: "bg-red-500/10" },
                      };
                      const config = typeConfig[event.type] || typeConfig.scan_completed;
                      const Icon = config.icon;
                      return (
                        <motion.div
                          key={i}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ duration: 0.3, delay: i * 0.05 }}
                          className="flex items-start gap-3 rounded-lg p-3 transition-colors hover:bg-secondary/30"
                          onClick={() => event.scan_id && router.push(`/scan/${event.scan_id}`)}
                        >
                          <div className={cn("mt-0.5 flex h-8 w-8 items-center justify-center rounded-lg flex-shrink-0", config.bg)}>
                            <Icon className={cn("h-4 w-4", config.color)} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-foreground leading-tight">{event.description}</p>
                            <p className="text-xs text-muted-foreground mt-0.5">{event.time}</p>
                          </div>
                        </motion.div>
                      );
                    })
                  )}
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Quick Actions */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.5 }}
          >
            <Card className="glass h-full">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">Quick Actions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Link href="/scan/new" className="block">
                  <Button className="w-full justify-start gap-3 h-12 bg-gradient-to-r from-primary to-cyan-500 hover:from-primary/90 hover:to-cyan-500/90 shadow-lg shadow-primary/20">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10">
                      <Zap className="h-4 w-4" />
                    </div>
                    <div className="text-left">
                      <p className="font-medium text-sm">New Scan</p>
                      <p className="text-xs text-white/70">Discover attack surface</p>
                    </div>
                  </Button>
                </Link>
                <Link href="/scans" className="block">
                  <Button variant="outline" className="w-full justify-start gap-3 h-12 border-border/50 hover:bg-secondary/50">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10">
                      <LayoutGrid className="h-4 w-4 text-emerald-400" />
                    </div>
                    <div className="text-left">
                      <p className="font-medium text-sm">View Assets</p>
                      <p className="text-xs text-muted-foreground">Browse all discovered assets</p>
                    </div>
                  </Button>
                </Link>
                <Link href="/reports" className="block">
                  <Button variant="outline" className="w-full justify-start gap-3 h-12 border-border/50 hover:bg-secondary/50">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-500/10">
                      <FileText className="h-4 w-4 text-purple-400" />
                    </div>
                    <div className="text-left">
                      <p className="font-medium text-sm">Generate Report</p>
                      <p className="text-xs text-muted-foreground">Export security report</p>
                    </div>
                  </Button>
                </Link>

                <div className="pt-3 border-t border-border/30">
                  <p className="text-xs text-muted-foreground mb-3 font-medium uppercase tracking-wider">
                    Quick Scan
                  </p>
                  <QuickScanForm />
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* Recent Scans Table */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.6 }}
        >
          <Card className="glass">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-sm font-medium">Recent Scans</CardTitle>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Your latest reconnaissance scans
                  </p>
                </div>
                {scans.length > 0 && (
                  <Link href="/scans">
                    <Button variant="ghost" size="sm" className="text-xs gap-1 h-8">
                      View All
                      <ArrowRight className="h-3 w-3" />
                    </Button>
                  </Link>
                )}
              </div>
            </CardHeader>
            <CardContent>
              <RecentScansTable scans={scans} loading={loading} />
            </CardContent>
          </Card>
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
