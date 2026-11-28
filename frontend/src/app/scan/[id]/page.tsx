"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { Suspense } from "react";
import {
  ArrowLeft,
  RefreshCw,
  Loader2,
  Globe,
  Server,
  Lock,
  AlertTriangle,
  CheckCircle,
  Clock,
  Trash2,
  Download,
  Search,
  ExternalLink,
  Shield,
  Cpu,
  FileText,
  X,
  ChevronRight,
  Bug,
} from "lucide-react";
import {
  getScan,
  listPorts,
  listSSLCertificates,
  listSubdomains,
  listTechnologies,
  listVulnerabilities,
  deleteScan,
  exportToCSV,
} from "@/lib/api";
import {
  Badge,
} from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PageHeader } from "@/components/common/PageHeader";
import { ScanTerminal } from "@/components/scan/ScanTerminal";
import type {
  ScanDetail,
  Subdomain,
  Port,
  SSLCertificate,
  Technology,
  Vulnerability,
  RiskScore,
} from "@/types";
import { getRiskLabel, getRiskColor } from "@/types";

interface ModuleStatus {
  name: string;
  status: "pending" | "running" | "completed" | "failed";
}

function ScanDetailContent() {
  const params = useParams();
  const router = useRouter();
  const scanId = params.id as string;

  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [subdomains, setSubdomains] = useState<Subdomain[]>([]);
  const [ports, setPorts] = useState<Port[]>([]);
  const [sslCerts, setSslCerts] = useState<SSLCertificate[]>([]);
  const [technologies, setTechnologies] = useState<Technology[]>([]);
  const [vulnerabilities, setVulnerabilities] = useState<Vulnerability[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleteDialog, setDeleteDialog] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const [subdomainSearch, setSubdomainSearch] = useState("");
  const [portSearch, setPortSearch] = useState("");
  const [techSearch, setTechSearch] = useState("");
  const [techFilter, setTechFilter] = useState("all");

  const fetchScan = useCallback(async () => {
    try {
      const detail = await getScan(scanId);
      setScan(detail);

      const [subs, p, ssl, techs, vulns] = await Promise.all([
        listSubdomains(scanId),
        listPorts(scanId),
        listSSLCertificates(scanId),
        listTechnologies(scanId),
        listVulnerabilities(scanId),
      ]);
      setSubdomains(subs);
      setPorts(p);
      setSslCerts(ssl);
      setTechnologies(techs);
      setVulnerabilities(vulns);
    } catch {
    } finally {
      setLoading(false);
    }
  }, [scanId]);

  useEffect(() => {
    fetchScan();
  }, [fetchScan]);

  useEffect(() => {
    // Poll while the scan is queued or running; a queued scan starts on its own.
    if (!scan || (scan.status !== "running" && scan.status !== "pending")) return;
    const interval = setInterval(fetchScan, 2000);
    return () => clearInterval(interval);
  }, [scan?.status, fetchScan]);

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await deleteScan(scanId);
      router.push("/scans");
    } catch {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-brand" />
          <p className="text-sm text-muted-foreground">Loading scan results...</p>
        </div>
      </div>
    );
  }

  if (!scan) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4">
        <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-muted/50">
          <AlertTriangle className="h-8 w-8 text-muted-foreground" />
        </div>
        <p className="text-muted-foreground">Scan not found.</p>
        <Link href="/scans">
          <Button variant="outline">Back to scans</Button>
        </Link>
      </div>
    );
  }

  const isQueued = scan.status === "pending";
  const isRunning = scan.status === "running" || isQueued;
  const isCompleted = scan.status === "completed";
  const riskLabel = scan.risk_score !== null ? getRiskLabel(scan.risk_score) : null;
  const riskColorClass = scan.risk_score !== null ? getRiskColor(scan.risk_score) : "";

  const modules: ModuleStatus[] = isRunning
    ? [
        { name: "Subdomain Discovery", status: scan.progress > 30 ? "completed" : scan.progress > 0 ? "running" : "pending" },
        { name: "Port Scanning", status: scan.progress > 50 ? "completed" : scan.progress > 30 ? "running" : "pending" },
        { name: "SSL Analysis", status: scan.progress > 70 ? "completed" : scan.progress > 50 ? "running" : "pending" },
        { name: "WHOIS Lookup", status: scan.progress > 85 ? "completed" : scan.progress > 70 ? "running" : "pending" },
        { name: "Technology Detection", status: scan.progress > 95 ? "completed" : scan.progress > 85 ? "running" : "pending" },
      ]
    : [];

  const filteredSubdomains = subdomains.filter(
    (s) => !subdomainSearch || s.hostname.toLowerCase().includes(subdomainSearch.toLowerCase())
  );

  const filteredPorts = ports.filter(
    (p) =>
      !portSearch ||
      p.hostname.toLowerCase().includes(portSearch.toLowerCase()) ||
      String(p.port_number).includes(portSearch) ||
      (p.service || "").toLowerCase().includes(portSearch.toLowerCase())
  );

  const filteredTechs = technologies.filter(
    (t) =>
      (techFilter === "all" || t.category === techFilter) &&
      (!techSearch || t.name.toLowerCase().includes(techSearch.toLowerCase()))
  );

  const techCategories = Array.from(new Set(technologies.map((t) => t.category).filter(Boolean)));

  const getGradeColor = (grade: string | null) => {
    if (!grade) return "text-muted-foreground bg-muted/50";
    if (grade.startsWith("A")) return "text-success bg-success/10";
    if (grade === "B") return "text-warning bg-warning/10";
    return "text-destructive bg-destructive/10";
  };

  const getServiceColor = (service: string | null) => {
    if (!service) return "text-muted-foreground";
    const s = service.toLowerCase();
    if (s.includes("http")) return "text-success";
    if (s.includes("ssl") || s.includes("tls") || s.includes("https")) return "text-info";
    if (s.includes("ssh")) return "text-warning";
    if (s.includes("dns")) return "text-accent-2";
    if (s.includes("smtp") || s.includes("mail")) return "text-brand-2";
    if (s.includes("ftp")) return "text-warning";
    return "text-muted-foreground";
  };

  return (
    <div className="page-container-lg">
      <div className="py-6 space-y-6">
        <PageHeader
          title={scan.domain}
          description={
            <>
              {new Date(scan.created_at).toLocaleString()}
              {scan.completed_at && ` · Completed in ${Math.round((new Date(scan.completed_at).getTime() - new Date(scan.created_at).getTime()) / 60000)}min`}
            </>
          }
          icon={<Globe className="h-5 w-5" />}
          breadcrumbs={[{ label: "Home", href: "/dashboard" }, { label: "Scans", href: "/scans" }, { label: scan.domain }]}
          actions={
            <div className="flex items-center gap-2">
              <Badge
                variant={
                  scan.status === "completed"
                    ? "success"
                    : scan.status === "running"
                      ? "info"
                      : scan.status === "failed"
                        ? "destructive"
                        : "secondary"
                }
                className="capitalize"
              >
                {scan.status}
              </Badge>
              <Badge variant="secondary" className="capitalize">{scan.scan_type} scan</Badge>
              <Button
                variant="outline"
                size="sm"
                onClick={() => fetchScan()}
                disabled={isRunning}
                className="gap-1.5 rounded-lg"
              >
                <RefreshCw className={cn("h-3.5 w-3.5", isRunning && "animate-spin")} />
                Refresh
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5 rounded-lg"
                onClick={() => {
                  exportToCSV(
                    subdomains.map((s) => ({
                      hostname: s.hostname,
                      ip_addresses: (s.ip_addresses || []).join("; "),
                      is_alive: s.is_alive,
                    })),
                    `subdomains-${scan.domain}`
                  );
                }}
              >
                <Download className="h-3.5 w-3.5" />
                Export
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setDeleteDialog(true)}
                className="gap-1.5 rounded-lg text-destructive hover:text-destructive hover:bg-destructive/10"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          }
        />

      <div className="space-y-6">
        {/* Running Progress */}
        {isRunning && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border border-border bg-card p-6 shadow-elevation-1"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <ScanTerminal
                  queued={isQueued}
                  hosts={subdomains.map((s) => ({ name: s.hostname, ip: s.ip_addresses?.[0] }))}
                  ports={ports.map((p) => ({
                    port: p.port_number,
                    service: p.service,
                    host: subdomains.find((s) => s.id === p.subdomain_id)?.hostname,
                  }))}
                  className="hidden sm:block"
                />
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand/10 sm:hidden">
                  <Loader2 className="h-5 w-5 text-brand animate-spin" />
                </div>
                <div>
                  <p className="font-semibold">{isQueued ? "Waiting to start" : "Scan in progress"}</p>
                  <p className="text-sm text-muted-foreground">
                    {isQueued
                      ? "Your scan is queued and will start shortly. This page updates on its own."
                      : "Discovering your attack surface. Results appear below as they are found."}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-3xl font-semibold tabular-nums">{scan.progress}%</p>
                <p className="text-xs text-muted-foreground">{isQueued ? "In queue" : `About ${Math.max(1, Math.round((100 - scan.progress) / 10))} min left`}</p>
              </div>
            </div>

            <Progress
              value={scan.progress}
              className="h-2 mb-6"
              indicatorClassName="bg-primary"
            />

            <div className="space-y-2">
              {modules.map((mod) => (
                <div key={mod.name} className="flex items-center gap-3">
                  {mod.status === "completed" ? (
                    <div className="flex h-5 w-5 items-center justify-center rounded-full bg-success/20">
                      <CheckCircle className="h-3.5 w-3.5 text-success" />
                    </div>
                  ) : mod.status === "running" ? (
                    <div className="flex h-5 w-5 items-center justify-center rounded-full bg-brand/20">
                      <Loader2 className="h-3.5 w-3.5 text-brand animate-spin" />
                    </div>
                  ) : (
                    <div className="flex h-5 w-5 items-center justify-center rounded-full bg-muted">
                      <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                    </div>
                  )}
                  <span
                    className={cn(
                      "text-sm",
                      mod.status === "completed"
                        ? "text-foreground"
                        : mod.status === "running"
                          ? "text-brand font-medium"
                          : "text-muted-foreground"
                    )}
                  >
                    {mod.name}
                  </span>
                  {mod.status === "completed" && (
                    <span className="text-[10px] text-success ml-auto">Done</span>
                  )}
                  {mod.status === "running" && (
                    <span className="text-[10px] text-brand ml-auto">In progress</span>
                  )}
                </div>
              ))}
            </div>
          </motion.div>
        )}

        {/* Summary: risk score, findings by severity, inventory counts */}
        {isCompleted && (
          <section className="grid gap-4 lg:grid-cols-[auto_1fr_1fr]">
            {scan.risk_score !== null && (
              <div className="flex items-center gap-5 rounded-xl border border-border bg-card p-5 shadow-elevation-1">
                <div className="relative shrink-0">
                  <svg width="96" height="96" viewBox="0 0 120 120" className="-rotate-90" role="img" aria-label={`Risk score ${scan.risk_score} out of 100`}>
                    <circle cx="60" cy="60" r="50" fill="none" stroke="hsl(var(--muted))" strokeWidth="10" />
                    <circle
                      cx="60"
                      cy="60"
                      r="50"
                      fill="none"
                      strokeWidth="10"
                      strokeLinecap="round"
                      strokeDasharray={`${(scan.risk_score / 100) * 314} 314`}
                      className="score-circle"
                      style={{
                        stroke:
                          scan.risk_score <= 25
                            ? "hsl(var(--success))"
                            : scan.risk_score <= 50
                              ? "hsl(var(--sev-medium))"
                              : scan.risk_score <= 75
                                ? "hsl(var(--sev-high))"
                                : "hsl(var(--sev-critical))",
                      }}
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-2xl font-semibold tabular-nums">{scan.risk_score}</span>
                  </div>
                </div>
                <div className="pr-4">
                  <p className="text-[13px] font-medium text-muted-foreground">Risk score</p>
                  <p className="mt-0.5 text-xl font-semibold tracking-tight">{riskLabel} risk</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">out of 100, higher is worse</p>
                </div>
              </div>
            )}

            <div className="rounded-xl border border-border bg-card p-5 shadow-elevation-1">
              <div className="flex items-baseline justify-between">
                <p className="text-[13px] font-medium text-muted-foreground">Findings</p>
                <p className="text-xl font-semibold tabular-nums">{vulnerabilities.length}</p>
              </div>
              {(() => {
                const sev = [
                  { k: "critical", l: "Critical", c: "bg-severity-critical" },
                  { k: "high", l: "High", c: "bg-severity-high" },
                  { k: "medium", l: "Medium", c: "bg-severity-medium" },
                  { k: "low", l: "Low", c: "bg-severity-low" },
                ].map((x) => ({ ...x, n: vulnerabilities.filter((v) => v.severity === x.k).length }));
                const total = Math.max(1, vulnerabilities.length);
                return (
                  <>
                    <div className="mt-3 flex h-2 overflow-hidden rounded-full bg-muted">
                      {sev.map((x) => x.n > 0 && <div key={x.k} className={x.c} style={{ width: `${(x.n / total) * 100}%` }} />)}
                    </div>
                    <dl className="mt-4 grid grid-cols-4 gap-2">
                      {sev.map((x) => (
                        <div key={x.k}>
                          <dt className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            <span className={cn("h-2 w-2 rounded-sm", x.c)} aria-hidden="true" />
                            {x.l}
                          </dt>
                          <dd className="mt-0.5 text-base font-semibold tabular-nums">{x.n}</dd>
                        </div>
                      ))}
                    </dl>
                  </>
                );
              })()}
            </div>

            <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border bg-border shadow-elevation-1">
              {[
                { label: "Subdomains", value: subdomains.length, icon: Globe },
                { label: "Open ports", value: ports.length, icon: Server },
                { label: "TLS certificates", value: sslCerts.length, icon: Lock },
                { label: "Technologies", value: technologies.length, icon: Cpu },
              ].map((stat) => (
                <div key={stat.label} className="flex items-center gap-3 bg-card px-4 py-3">
                  <stat.icon className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <div>
                    <p className="text-lg font-semibold leading-tight tabular-nums">{stat.value}</p>
                    <p className="text-xs text-muted-foreground">{stat.label}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Scanner Status Panel */}
        {isCompleted && scan.scanner_status && Object.keys(scan.scanner_status).length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border border-border bg-card p-5 shadow-elevation-1"
          >
            <div className="flex items-center gap-2 mb-3">
              <Cpu className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-sm font-semibold text-foreground">Scan stages</h3>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {Object.entries(scan.scanner_status).map(([scanner, status]) => {
                const statusLower = (status as string).toLowerCase();
                const color =
                  statusLower.startsWith("ok")
                    ? "text-success bg-success/10 border-success/20"
                    : statusLower.startsWith("skipped") || statusLower.startsWith("not installed") || statusLower.startsWith("no_records") || statusLower.startsWith("removed")
                      ? "text-muted-foreground bg-muted/30 border-border"
                      : statusLower.startsWith("partial") || statusLower.startsWith("blocked") || statusLower.startsWith("rate") || statusLower.startsWith("limited") || statusLower.startsWith("resolution_failed")
                        ? "text-warning bg-warning/10 border-warning/20"
                        : statusLower.startsWith("failed") || statusLower.startsWith("error")
                          ? "text-destructive bg-destructive/10 border-destructive/20"
                          : "text-muted-foreground bg-muted/30 border-border";
                return (
                  <div
                    key={scanner}
                    className={cn(
                      "flex items-center justify-between rounded-lg border px-3 py-2 text-xs",
                      color
                    )}
                  >
                    <span className="font-medium font-mono truncate mr-2">{scanner}</span>
                    <span className="truncate text-right shrink-0">{status as string}</span>
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}

        {/* Tabs */}
        <Tabs defaultValue="subdomains">
          <TabsList>
            <TabsTrigger value="subdomains">
              <Globe className="h-3.5 w-3.5" />
              Subdomains
              <Badge variant="secondary" className="ml-1 text-[10px] px-1.5 py-0">{subdomains.length}</Badge>
            </TabsTrigger>
            <TabsTrigger value="ports">
              <Server className="h-3.5 w-3.5" />
              Ports
              <Badge variant="secondary" className="ml-1 text-[10px] px-1.5 py-0">{ports.length}</Badge>
            </TabsTrigger>
            <TabsTrigger value="ssl">
              <Lock className="h-3.5 w-3.5" />
              TLS
              <Badge variant="secondary" className="ml-1 text-[10px] px-1.5 py-0">{sslCerts.length}</Badge>
            </TabsTrigger>
            <TabsTrigger value="technologies">
              <Cpu className="h-3.5 w-3.5" />
              Technologies
              <Badge variant="secondary" className="ml-1 text-[10px] px-1.5 py-0">{technologies.length}</Badge>
            </TabsTrigger>
            <TabsTrigger value="vulnerabilities">
              <Bug className="h-3.5 w-3.5" />
              Findings
              <Badge variant="secondary" className="ml-1 text-[10px] px-1.5 py-0">{vulnerabilities.length}</Badge>
            </TabsTrigger>
          </TabsList>

          {/* Subdomains Tab */}
          <TabsContent value="subdomains">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="overflow-hidden rounded-xl border border-border bg-card shadow-elevation-1">
              <div className="flex items-center justify-between p-4 border-b border-border">
                <h3 className="text-sm font-semibold">Discovered Subdomains</h3>
                <div className="flex items-center gap-2">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                    <input
                      placeholder="Search subdomains..."
                      value={subdomainSearch}
                      onChange={(e) => setSubdomainSearch(e.target.value)}
                      className="h-8 w-56 rounded-md border border-input bg-background pl-9 pr-3 text-[13px] focus:border-primary focus:outline-none focus:ring-2 focus:ring-ring/30"
                    />
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-1 text-xs rounded-lg"
                    onClick={() =>
                      exportToCSV(
                        filteredSubdomains.map((s) => ({
                          hostname: s.hostname,
                          ip_addresses: (s.ip_addresses || []).join("; "),
                          is_alive: s.is_alive,
                        })),
                        `subdomains-${scan.domain}`
                      )
                    }
                  >
                    <Download className="h-3 w-3" />
                    Export
                  </Button>
                </div>
              </div>

              {filteredSubdomains.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16">
                  <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-muted/50 mb-3">
                    <Globe className="h-7 w-7 text-muted-foreground" />
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {isRunning ? "Discovering subdomains..." : "No subdomains found"}
                  </p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead >Hostname</TableHead>
                      <TableHead >IP Addresses</TableHead>
                      <TableHead >Status</TableHead>
                      <TableHead >Discovered</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredSubdomains.map((sub) => (
                      <TableRow key={sub.id} >
                        <TableCell className="font-mono text-xs">{sub.hostname}</TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {sub.ip_addresses.join(", ") || "—"}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={sub.is_alive ? "success" : "secondary"}
                            className="text-[10px] px-1.5 py-0"
                          >
                            {sub.is_alive ? "alive" : "unknown"}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {new Date(sub.discovered_at).toLocaleDateString()}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </motion.div>
          </TabsContent>

          {/* Ports Tab */}
          <TabsContent value="ports">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="overflow-hidden rounded-xl border border-border bg-card shadow-elevation-1">
              <div className="flex items-center justify-between p-4 border-b border-border">
                <h3 className="text-sm font-semibold">Open Ports</h3>
                <div className="flex items-center gap-2">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                    <input
                      placeholder="Search ports, services..."
                      value={portSearch}
                      onChange={(e) => setPortSearch(e.target.value)}
                      className="h-8 w-56 rounded-md border border-input bg-background pl-9 pr-3 text-[13px] focus:border-primary focus:outline-none focus:ring-2 focus:ring-ring/30"
                    />
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-1 text-xs rounded-lg"
                    onClick={() => {
                      exportToCSV(
                        filteredPorts.map((p) => ({
                          hostname: p.hostname,
                          port: p.port_number,
                          state: p.state,
                          service: p.service || "",
                          version: p.version || "",
                        })),
                        `ports-${scan.domain}`
                      );
                    }}
                  >
                    <Download className="h-3 w-3" />
                    Export
                  </Button>
                </div>
              </div>

              {filteredPorts.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16">
                  <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-muted/50 mb-3">
                    <Server className="h-7 w-7 text-muted-foreground" />
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {isRunning ? "Scanning ports..." : "No open ports found"}
                  </p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead >Host</TableHead>
                      <TableHead >Port</TableHead>
                      <TableHead >Service</TableHead>
                      <TableHead >Version</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredPorts.map((port) => (
                      <TableRow key={port.id} >
                        <TableCell className="font-mono text-xs">{port.hostname}</TableCell>
                        <TableCell>
                          <Badge variant="outline" className="font-mono text-xs px-2 py-0">
                            {port.port_number}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <span className={cn("text-xs font-medium", getServiceColor(port.service))}>
                            {port.service || "—"}
                          </span>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {port.version || "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </motion.div>
          </TabsContent>

          {/* SSL Tab */}
          <TabsContent value="ssl">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="overflow-hidden rounded-xl border border-border bg-card shadow-elevation-1">
              <div className="flex items-center justify-between p-4 border-b border-border">
                <h3 className="text-sm font-semibold">SSL Certificates</h3>
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-1 text-xs rounded-lg"
                    onClick={() => {
                      exportToCSV(
                        sslCerts.map((c) => ({
                          hostname: c.hostname,
                          issuer: c.issuer || "",
                          subject: c.subject || "",
                          not_before: c.not_before || "",
                          not_after: c.not_after || "",
                          is_valid: c.is_valid,
                          grade: c.grade || "",
                        })),
                        `ssl-certificates-${scan.domain}`
                      );
                    }}
                  >
                    <Download className="h-3 w-3" />
                    Export
                  </Button>
              </div>

              {sslCerts.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16">
                  <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-muted/50 mb-3">
                    <Lock className="h-7 w-7 text-muted-foreground" />
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {isRunning ? "Checking certificates..." : "No SSL certificates found"}
                  </p>
                </div>
              ) : (
                <div className="p-4 grid gap-3 md:grid-cols-2">
                  {sslCerts.map((cert) => {
                    const isExpiringSoon =
                      cert.not_after &&
                      new Date(cert.not_after).getTime() - Date.now() < 30 * 24 * 60 * 60 * 1000;
                    return (
                      <div
                        key={cert.id}
                        className={cn(
                          "rounded-xl border p-4 transition-all",
                          isExpiringSoon ? "border-warning/30" : "border-border"
                        )}
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="min-w-0 flex-1">
                            <p className="font-mono text-sm font-medium truncate">
                              {cert.hostname}
                            </p>
                            <p className="text-xs text-muted-foreground mt-0.5">
                              {cert.issuer || "Unknown issuer"}
                            </p>
                          </div>
                          <div className={cn("flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-semibold shrink-0", getGradeColor(cert.grade))}>
                            {cert.grade || "N/A"}
                          </div>
                        </div>
                        <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground">
                          {cert.protocol && (
                            <span className="bg-muted/50 px-2 py-0.5 rounded">{cert.protocol}</span>
                          )}
                          {cert.not_after && (
                            <span className={cn(isExpiringSoon && "text-warning font-medium")}>
                              Expires: {new Date(cert.not_after).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </motion.div>
          </TabsContent>

          {/* Technologies Tab */}
          <TabsContent value="technologies">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="overflow-hidden rounded-xl border border-border bg-card shadow-elevation-1">
              <div className="flex items-center justify-between p-4 border-b border-border">
                <h3 className="text-sm font-semibold">Detected Technologies</h3>
                <div className="flex items-center gap-2">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                    <input
                      placeholder="Search technologies..."
                      value={techSearch}
                      onChange={(e) => setTechSearch(e.target.value)}
                      className="h-8 w-56 rounded-md border border-input bg-background pl-9 pr-3 text-[13px] focus:border-primary focus:outline-none focus:ring-2 focus:ring-ring/30"
                    />
                  </div>
                  <select
                    value={techFilter}
                    onChange={(e) => setTechFilter(e.target.value)}
                    className="h-8 px-3 rounded-lg bg-muted/50 border border-border text-xs focus:border-brand/30 focus:outline-none appearance-none cursor-pointer"
                  >
                    <option value="all">All categories</option>
                    {techCategories.map((cat) => (
                      <option key={cat} value={cat!}>{cat}</option>
                    ))}
                  </select>
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-1 text-xs rounded-lg"
                    onClick={() => {
                      exportToCSV(
                        filteredTechs.map((t) => ({
                          hostname: t.hostname,
                          name: t.name,
                          category: t.category || "",
                          version: t.version || "",
                          confidence: t.confidence,
                        })),
                        `technologies-${scan.domain}`
                      );
                    }}
                  >
                    <Download className="h-3 w-3" />
                    Export
                  </Button>
                </div>
              </div>

              {filteredTechs.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16">
                  <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-muted/50 mb-3">
                    <Cpu className="h-7 w-7 text-muted-foreground" />
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {isRunning ? "Detecting technologies..." : "No technologies found"}
                  </p>
                </div>
              ) : (
                <div className="p-4 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                  {filteredTechs.map((tech) => (
                    <div
                      key={tech.id}
                      className="rounded-xl border border-border p-4 transition-all"
                    >
                      <div className="flex items-start justify-between mb-2">
                        <p className="font-medium text-sm">{tech.name}</p>
                        {tech.category && (
                          <Badge variant="secondary" className="text-[10px] px-1.5 py-0 shrink-0">
                            {tech.category}
                          </Badge>
                        )}
                      </div>
                      <div className="space-y-2">
                        {tech.version && (
                          <p className="text-xs text-muted-foreground">v{tech.version}</p>
                        )}
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                            <div
                              className="h-full bg-brand/60 rounded-full"
                              style={{ width: `${tech.confidence}%` }}
                            />
                          </div>
                          <span className="text-[10px] text-muted-foreground">
                            {tech.confidence}%
                          </span>
                        </div>
                        <p className="text-[10px] text-muted-foreground truncate">
                          {tech.hostname}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </motion.div>
          </TabsContent>

          {/* Vulnerabilities Tab */}
          <TabsContent value="vulnerabilities">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="overflow-hidden rounded-xl border border-border bg-card shadow-elevation-1">
              <div className="flex items-center justify-between p-4 border-b border-border">
                <h3 className="text-sm font-semibold">Discovered Vulnerabilities</h3>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-1 text-xs rounded-lg"
                  onClick={() => {
                    exportToCSV(
                      vulnerabilities.map((v) => ({
                        name: v.name,
                        severity: v.severity,
                        host: v.host,
                        matched_at: v.matched_at || "",
                        description: v.description || "",
                        template_id: v.template_id,
                        tags: (v.tags || []).join("; "),
                      })),
                      `vulnerabilities-${scan.domain}`
                    );
                  }}
                >
                  <Download className="h-3 w-3" />
                  Export
                </Button>
              </div>

              {vulnerabilities.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16">
                  <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-muted/50 mb-3">
                    <Bug className="h-7 w-7 text-muted-foreground" />
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {isRunning ? "Scanning for vulnerabilities..." : "No vulnerabilities found"}
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-border/30">
                  {vulnerabilities.map((vuln) => (
                    <div key={vuln.id} className="p-4 transition-all">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <Badge
                              variant={vuln.severity === "critical" ? "destructive" : vuln.severity === "high" ? "warning" : vuln.severity === "medium" ? "default" : "secondary"}
                              className={cn("text-[10px] px-1.5 py-0 shrink-0", vuln.severity === "critical" && "shadow-[0_0_8px_hsl(var(--destructive)/0.3)]")}
                            >
                              {vuln.severity?.toUpperCase()}
                            </Badge>
                            <p className="font-medium text-sm truncate">{vuln.name}</p>
                          </div>
                          <p className="text-xs text-muted-foreground mb-1 truncate">
                            {vuln.host} {vuln.matched_at ? `→ ${vuln.matched_at}` : ""}
                          </p>
                          {vuln.description && (
                            <p className="text-xs text-muted-foreground line-clamp-2">{vuln.description}</p>
                          )}
                        </div>
                        {vuln.reference && (
                          <a
                            href={Array.isArray(vuln.reference) ? vuln.reference[0] : vuln.reference}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-brand hover:text-brand/80 shrink-0"
                          >
                            <ExternalLink className="h-4 w-4" />
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </motion.div>
          </TabsContent>
        </Tabs>
      </div>

      {/* Delete Dialog */}
      <Dialog open={deleteDialog} onOpenChange={setDeleteDialog}>
        <DialogContent className="glass-strong">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              Delete Scan
            </DialogTitle>
            <DialogDescription>
              Are you sure you want to delete the scan for{" "}
              <span className="font-semibold text-foreground">{scan.domain}</span>?
              All associated data will be permanently removed.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-3 mt-4">
            <Button variant="outline" onClick={() => setDeleteDialog(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleting}
              className="gap-2"
            >
              {deleting && <Loader2 className="h-4 w-4 animate-spin" />}
              Delete Scan
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      </div>
    </div>
  );
}

export default function ScanDetailPage() {
  return (
    <ProtectedRoute>
      <Suspense fallback={
        <div className="flex h-screen items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      }>
        <ScanDetailContent />
      </Suspense>
    </ProtectedRoute>
  );
}
