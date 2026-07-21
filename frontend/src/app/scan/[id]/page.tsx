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
    if (!scan || scan.status !== "running") return;
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
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted/50">
          <AlertTriangle className="h-8 w-8 text-muted-foreground" />
        </div>
        <p className="text-muted-foreground">Scan not found.</p>
        <Link href="/scans">
          <Button variant="outline">Back to scans</Button>
        </Link>
      </div>
    );
  }

  const isRunning = scan.status === "running";
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
              <div className="flex items-center gap-1 text-[10px] text-muted-foreground bg-surface-2 px-2 py-1 rounded-full">
                <Shield className="h-3 w-3" />
                {scan.scan_type}
              </div>
              <Link href="/scans">
                <Button variant="ghost" size="icon" className="rounded-xl">
                  <ArrowLeft className="h-4 w-4" />
                </Button>
              </Link>
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
            className="glass-strong rounded-2xl p-6 gradient-border"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand/10">
                  <Loader2 className="h-5 w-5 text-brand animate-spin" />
                </div>
                <div>
                  <p className="font-semibold">Scan in Progress</p>
                  <p className="text-sm text-muted-foreground">
                    Discovering attack surface...
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-3xl font-bold gradient-text">{scan.progress}%</p>
                <p className="text-xs text-muted-foreground">Estimated: {Math.max(1, Math.round((100 - scan.progress) / 10))}min remaining</p>
              </div>
            </div>

            <Progress
              value={scan.progress}
              className="h-3 mb-6"
              indicatorClassName="bg-gradient-to-r gradient-brand"
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

        {/* Risk Score Hero */}
        {isCompleted && scan.risk_score !== null && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5 }}
            className="glass-strong rounded-2xl p-8 gradient-border"
          >
            <div className="flex flex-col md:flex-row items-center gap-8">
              {/* SVG Circle */}
              <div className="relative shrink-0">
                <svg width="160" height="160" viewBox="0 0 120 120" className="-rotate-90">
                  <circle
                    cx="60"
                    cy="60"
                    r="50"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="8"
                    className="text-muted/30"
                  />
                  <circle
                    cx="60"
                    cy="60"
                    r="50"
                    fill="none"
                    strokeWidth="8"
                    strokeLinecap="round"
                    strokeDasharray={`${(scan.risk_score / 100) * 314} 314`}
                    className="score-circle"
                    style={{
                      stroke:
                        scan.risk_score <= 25
                          ? "hsl(var(--success))"
                          : scan.risk_score <= 50
                            ? "hsl(var(--warning))"
                            : scan.risk_score <= 75
                              ? "hsl(25 90% 55%)"
                              : "hsl(var(--destructive))",
                    }}
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-4xl font-bold font-mono tabular-nums">{scan.risk_score}</span>
                  <span className="text-xs text-muted-foreground font-mono">/ 100</span>
                </div>
              </div>

              <div className="flex-1 space-y-4">
                <div>
                  <p className="text-sm text-muted-foreground mb-1">Risk Assessment</p>
                  <p className={cn("text-3xl font-bold", riskColorClass.split(" ")[0])}>
                    {riskLabel} Risk
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  {[
                    { label: "Subdomains", value: subdomains.length, icon: Globe },
                    { label: "Open Ports", value: ports.length, icon: Server },
                    { label: "SSL Certificates", value: sslCerts.length, icon: Lock },
                    { label: "Technologies", value: technologies.length, icon: Cpu },
                  ].map((stat) => (
                    <div key={stat.label} className="flex items-center gap-3 rounded-xl bg-muted/30 p-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted/50">
                        <stat.icon className="h-4 w-4 text-muted-foreground" />
                      </div>
                      <div>
                        <p className="text-lg font-bold font-mono tabular-nums">{stat.value}</p>
                        <p className="text-[10px] text-muted-foreground">{stat.label}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* Scanner Status Panel */}
        {isCompleted && scan.scanner_status && Object.keys(scan.scanner_status).length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass rounded-2xl p-5"
          >
            <div className="flex items-center gap-2 mb-3">
              <Cpu className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-sm font-semibold text-foreground">Scanner Health</h3>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {Object.entries(scan.scanner_status).map(([scanner, status]) => {
                const statusLower = (status as string).toLowerCase();
                const color =
                  statusLower.startsWith("ok")
                    ? "text-success bg-success/10 border-success/20"
                    : statusLower.startsWith("skipped") || statusLower.startsWith("not installed") || statusLower.startsWith("no_records") || statusLower.startsWith("removed")
                      ? "text-muted-foreground bg-muted/30 border-border/30"
                      : statusLower.startsWith("partial") || statusLower.startsWith("blocked") || statusLower.startsWith("rate") || statusLower.startsWith("limited") || statusLower.startsWith("resolution_failed")
                        ? "text-warning bg-warning/10 border-warning/20"
                        : statusLower.startsWith("failed") || statusLower.startsWith("error")
                          ? "text-destructive bg-destructive/10 border-destructive/20"
                          : "text-muted-foreground bg-muted/30 border-border/30";
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
          <TabsList className="glass rounded-xl p-1 h-auto w-full justify-start gap-1 flex-wrap">
            <TabsTrigger value="subdomains" className="gap-1.5 rounded-lg px-4 py-2 data-[state=active]:bg-brand/10 data-[state=active]:text-brand">
              <Globe className="h-3.5 w-3.5" />
              Subdomains
              <Badge variant="secondary" className="ml-1 text-[10px] px-1.5 py-0">{subdomains.length}</Badge>
            </TabsTrigger>
            <TabsTrigger value="ports" className="gap-1.5 rounded-lg px-4 py-2 data-[state=active]:bg-brand/10 data-[state=active]:text-brand">
              <Server className="h-3.5 w-3.5" />
              Ports
              <Badge variant="secondary" className="ml-1 text-[10px] px-1.5 py-0">{ports.length}</Badge>
            </TabsTrigger>
            <TabsTrigger value="ssl" className="gap-1.5 rounded-lg px-4 py-2 data-[state=active]:bg-brand/10 data-[state=active]:text-brand">
              <Lock className="h-3.5 w-3.5" />
              SSL
              <Badge variant="secondary" className="ml-1 text-[10px] px-1.5 py-0">{sslCerts.length}</Badge>
            </TabsTrigger>
            <TabsTrigger value="technologies" className="gap-1.5 rounded-lg px-4 py-2 data-[state=active]:bg-brand/10 data-[state=active]:text-brand">
              <Cpu className="h-3.5 w-3.5" />
              Technologies
              <Badge variant="secondary" className="ml-1 text-[10px] px-1.5 py-0">{technologies.length}</Badge>
            </TabsTrigger>
            <TabsTrigger value="vulnerabilities" className="gap-1.5 rounded-lg px-4 py-2 data-[state=active]:bg-brand/10 data-[state=active]:text-brand">
              <Bug className="h-3.5 w-3.5" />
              Vulnerabilities
              <Badge variant="secondary" className="ml-1 text-[10px] px-1.5 py-0">{vulnerabilities.length}</Badge>
            </TabsTrigger>
          </TabsList>

          {/* Subdomains Tab */}
          <TabsContent value="subdomains">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass rounded-xl overflow-hidden">
              <div className="flex items-center justify-between p-4 border-b border-border/30">
                <h3 className="font-semibold">Discovered Subdomains</h3>
                <div className="flex items-center gap-2">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                    <input
                      placeholder="Search subdomains..."
                      value={subdomainSearch}
                      onChange={(e) => setSubdomainSearch(e.target.value)}
                      className="h-8 pl-9 pr-3 rounded-lg bg-muted/50 border border-border/30 text-xs focus:border-brand/30 focus:outline-none w-52"
                    />
                  </div>
                  <Button variant="outline" size="sm" className="gap-1 text-xs rounded-lg">
                    <Download className="h-3 w-3" />
                    Export
                  </Button>
                </div>
              </div>

              {filteredSubdomains.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16">
                  <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted/50 mb-3">
                    <Globe className="h-7 w-7 text-muted-foreground" />
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {isRunning ? "Discovering subdomains..." : "No subdomains found"}
                  </p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow className="border-border/20 hover:bg-transparent">
                      <TableHead className="text-xs font-semibold">Hostname</TableHead>
                      <TableHead className="text-xs font-semibold">IP Addresses</TableHead>
                      <TableHead className="text-xs font-semibold">Status</TableHead>
                      <TableHead className="text-xs font-semibold">Discovered</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredSubdomains.map((sub) => (
                      <TableRow key={sub.id} className="border-border/10 hover:bg-muted/20">
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
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass rounded-xl overflow-hidden">
              <div className="flex items-center justify-between p-4 border-b border-border/30">
                <h3 className="font-semibold">Open Ports</h3>
                <div className="flex items-center gap-2">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                    <input
                      placeholder="Search ports, services..."
                      value={portSearch}
                      onChange={(e) => setPortSearch(e.target.value)}
                      className="h-8 pl-9 pr-3 rounded-lg bg-muted/50 border border-border/30 text-xs focus:border-brand/30 focus:outline-none w-52"
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
                  <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted/50 mb-3">
                    <Server className="h-7 w-7 text-muted-foreground" />
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {isRunning ? "Scanning ports..." : "No open ports found"}
                  </p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow className="border-border/20 hover:bg-transparent">
                      <TableHead className="text-xs font-semibold">Host</TableHead>
                      <TableHead className="text-xs font-semibold">Port</TableHead>
                      <TableHead className="text-xs font-semibold">Service</TableHead>
                      <TableHead className="text-xs font-semibold">Version</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredPorts.map((port) => (
                      <TableRow key={port.id} className="border-border/10 hover:bg-muted/20">
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
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass rounded-xl overflow-hidden">
              <div className="flex items-center justify-between p-4 border-b border-border/30">
                <h3 className="font-semibold">SSL Certificates</h3>
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
                  <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted/50 mb-3">
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
                          "rounded-xl border p-4 transition-all hover-glow",
                          isExpiringSoon ? "border-warning/30" : "border-border/30"
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
                          <div className={cn("flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-bold shrink-0", getGradeColor(cert.grade))}>
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
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass rounded-xl overflow-hidden">
              <div className="flex items-center justify-between p-4 border-b border-border/30">
                <h3 className="font-semibold">Detected Technologies</h3>
                <div className="flex items-center gap-2">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                    <input
                      placeholder="Search technologies..."
                      value={techSearch}
                      onChange={(e) => setTechSearch(e.target.value)}
                      className="h-8 pl-9 pr-3 rounded-lg bg-muted/50 border border-border/30 text-xs focus:border-brand/30 focus:outline-none w-52"
                    />
                  </div>
                  <select
                    value={techFilter}
                    onChange={(e) => setTechFilter(e.target.value)}
                    className="h-8 px-3 rounded-lg bg-muted/50 border border-border/30 text-xs focus:border-brand/30 focus:outline-none appearance-none cursor-pointer"
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
                  <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted/50 mb-3">
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
                      className="rounded-xl border border-border/30 p-4 hover-glow transition-all"
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
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass rounded-xl overflow-hidden">
              <div className="flex items-center justify-between p-4 border-b border-border/30">
                <h3 className="font-semibold">Discovered Vulnerabilities</h3>
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
                  <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted/50 mb-3">
                    <Bug className="h-7 w-7 text-muted-foreground" />
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {isRunning ? "Scanning for vulnerabilities..." : "No vulnerabilities found"}
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-border/30">
                  {vulnerabilities.map((vuln) => (
                    <div key={vuln.id} className="p-4 hover-glow transition-all">
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
