"use client";

import { useEffect, useState } from "react";
import {
  Globe,
  Server,
  Lock,
  Cpu,
  Search,
  LayoutGrid,
  TableIcon,
  AlertTriangle,
  Shield,
  Calendar,
  ArrowUpDown,
  ChevronUp,
  ChevronDown,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import api from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/StatusBadge";
import { FavoriteButton } from "@/components/FavoriteButton";
import type {
  Subdomain,
  Port,
  SSLCertificate,
  Technology,
} from "@/types";

type AssetFilter = "all" | "subdomains" | "ports" | "ssl" | "tech";
type ViewMode = "grid" | "table";
type SortField = "name" | "type" | "status" | "date";
type SortDir = "asc" | "desc";

interface UnifiedRow {
  type: "subdomain" | "port" | "ssl" | "tech";
  name: string;
  details: string;
  status: string;
  date: string;
  raw: Subdomain | Port | SSLCertificate | Technology;
}

function getGradeColor(grade: string | null): string {
  if (!grade) return "bg-zinc-500/10 text-zinc-400";
  if (grade.startsWith("A+")) return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
  if (grade.startsWith("A")) return "bg-blue-500/10 text-blue-400 border-blue-500/30";
  if (grade === "B") return "bg-amber-500/10 text-amber-400 border-amber-500/30";
  return "bg-red-500/10 text-red-400 border-red-500/30";
}

function getDaysUntil(dateStr: string | null): number | null {
  if (!dateStr) return null;
  const diff = new Date(dateStr).getTime() - Date.now();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

function AssetsContent() {
  const [searchQuery, setSearchQuery] = useState("");
  const [subdomains, setSubdomains] = useState<Subdomain[]>([]);
  const [ports, setPorts] = useState<Port[]>([]);
  const [sslCerts, setSslCerts] = useState<SSLCertificate[]>([]);
  const [technologies, setTechnologies] = useState<Technology[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState<AssetFilter>("all");
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [sortField, setSortField] = useState<SortField>("date");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  useEffect(() => {
    const fetchAssets = async () => {
      try {
        const [subRes, portRes, sslRes, techRes] = await Promise.all([
          api.get("/assets/subdomains"),
          api.get("/assets/ports"),
          api.get("/assets/ssl"),
          api.get("/assets/technologies"),
        ]);
        setSubdomains(subRes.data);
        setPorts(portRes.data);
        setSslCerts(sslRes.data);
        setTechnologies(techRes.data);
      } catch (error) {
        console.error("Failed to fetch assets:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchAssets();
  }, []);

  const query = searchQuery.toLowerCase();

  const filteredSubdomains = subdomains.filter((s) =>
    s.hostname.toLowerCase().includes(query)
  );
  const filteredPorts = ports.filter(
    (p) =>
      p.hostname.toLowerCase().includes(query) ||
      p.service?.toLowerCase().includes(query)
  );
  const filteredSsl = sslCerts.filter((c) =>
    c.hostname.toLowerCase().includes(query)
  );
  const filteredTech = technologies.filter(
    (t) =>
      t.name.toLowerCase().includes(query) ||
      t.hostname.toLowerCase().includes(query)
  );

  const hasAssets =
    filteredSubdomains.length > 0 ||
    filteredPorts.length > 0 ||
    filteredSsl.length > 0 ||
    filteredTech.length > 0;

  const showSubdomains =
    activeFilter === "all" || activeFilter === "subdomains";
  const showPorts = activeFilter === "all" || activeFilter === "ports";
  const showSsl = activeFilter === "all" || activeFilter === "ssl";
  const showTech = activeFilter === "all" || activeFilter === "tech";

  const unifiedRows: UnifiedRow[] = [];
  if (showSubdomains) {
    filteredSubdomains.forEach((s) =>
      unifiedRows.push({
        type: "subdomain",
        name: s.hostname,
        details: s.ip_addresses[0] || "—",
        status: s.is_alive ? "Alive" : "Unknown",
        date: s.discovered_at,
        raw: s,
      })
    );
  }
  if (showPorts) {
    filteredPorts.forEach((p) =>
      unifiedRows.push({
        type: "port",
        name: `${p.port_number}/${p.service || "unknown"}`,
        details: `${p.hostname} ${p.version ? `(${p.version})` : ""}`,
        status: p.state,
        date: p.scanned_at,
        raw: p,
      })
    );
  }
  if (showSsl) {
    filteredSsl.forEach((c) =>
      unifiedRows.push({
        type: "ssl",
        name: c.hostname,
        details: c.issuer || "Unknown issuer",
        status: c.grade || "N/A",
        date: c.scanned_at,
        raw: c,
      })
    );
  }
  if (showTech) {
    filteredTech.forEach((t) =>
      unifiedRows.push({
        type: "tech",
        name: t.name,
        details: `${t.category || "Unknown"} ${t.version ? `(${t.version})` : ""}`,
        status: `${t.confidence}%`,
        date: t.detected_at,
        raw: t,
      })
    );
  }

  const sorted = [...unifiedRows].sort((a, b) => {
    const dir = sortDir === "asc" ? 1 : -1;
    if (sortField === "name") return a.name.localeCompare(b.name) * dir;
    if (sortField === "type") return a.type.localeCompare(b.type) * dir;
    if (sortField === "status") return a.status.localeCompare(b.status) * dir;
    return (new Date(a.date).getTime() - new Date(b.date).getTime()) * dir;
  });

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field)
      return <ArrowUpDown className="h-3 w-3 opacity-40" />;
    return sortDir === "asc" ? (
      <ChevronUp className="h-3 w-3" />
    ) : (
      <ChevronDown className="h-3 w-3" />
    );
  };

  const filterCounts = {
    all:
      filteredSubdomains.length +
      filteredPorts.length +
      filteredSsl.length +
      filteredTech.length,
    subdomains: filteredSubdomains.length,
    ports: filteredPorts.length,
    ssl: filteredSsl.length,
    tech: filteredTech.length,
  };

  return (
    <div className="min-h-screen">
      <div className="border-b border-border/50 bg-card/30 backdrop-blur-xl sticky top-0 z-10">
        <div className="mx-auto max-w-7xl px-6 py-5">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Assets</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                All discovered subdomains, ports, certificates, and technologies.
              </p>
            </div>
            <div className="flex items-center gap-1 rounded-lg border border-border/50 bg-muted/30 p-1">
              <button
                onClick={() => setViewMode("grid")}
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-md transition-all",
                  viewMode === "grid"
                    ? "bg-primary text-primary-foreground shadow"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                <LayoutGrid className="h-4 w-4" />
              </button>
              <button
                onClick={() => setViewMode("table")}
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-md transition-all",
                  viewMode === "table"
                    ? "bg-primary text-primary-foreground shadow"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                <TableIcon className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-6 py-8">
        <div className="mb-6 relative">
          <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search assets by hostname, service, or technology..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-11 pl-11 bg-muted/30 border-border/50 focus:border-primary/50 focus:ring-primary/20"
          />
        </div>

        <div className="mb-6 flex flex-wrap gap-2">
          {(
            ["all", "subdomains", "ports", "ssl", "tech"] as AssetFilter[]
          ).map((filter) => {
            const icons = {
              all: Globe,
              subdomains: Globe,
              ports: Server,
              ssl: Lock,
              tech: Cpu,
            };
            const labels = {
              all: "All",
              subdomains: "Subdomains",
              ports: "Ports",
              ssl: "SSL",
              tech: "Technologies",
            };
            const Icon = icons[filter];
            const count = filterCounts[filter];
            return (
              <button
                key={filter}
                onClick={() => setActiveFilter(filter)}
                className={cn(
                  "flex items-center gap-2 rounded-lg border px-3.5 py-2 text-sm font-medium transition-all",
                  activeFilter === filter
                    ? "border-primary/50 bg-primary/10 text-primary shadow-sm"
                    : "border-border/50 bg-muted/30 text-muted-foreground hover:border-border hover:text-foreground"
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {labels[filter]}
                <span
                  className={cn(
                    "rounded-md px-1.5 py-0.5 text-xs font-semibold",
                    activeFilter === filter
                      ? "bg-primary/20 text-primary"
                      : "bg-muted text-muted-foreground"
                  )}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        <AnimatePresence mode="wait">
          {loading ? (
            <motion.div
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
            >
              {Array.from({ length: 6 }).map((_, i) => (
                <div
                  key={i}
                  className="h-44 rounded-xl skeleton"
                />
              ))}
            </motion.div>
          ) : !hasAssets ? (
            <motion.div
              key="empty"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="flex flex-col items-center justify-center py-24 text-center"
            >
              <div className="relative mb-6">
                <div className="absolute inset-0 rounded-full bg-primary/20 blur-2xl" />
                <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl border border-border/50 bg-card/80">
                  <Globe className="h-10 w-10 text-muted-foreground" />
                </div>
              </div>
              <h3 className="text-xl font-semibold mb-2">
                No assets discovered yet
              </h3>
              <p className="text-sm text-muted-foreground max-w-sm mb-6">
                Start a scan to discover subdomains, open ports, SSL
                certificates, and technologies for your attack surface.
              </p>
              <a
                href="/scan/new"
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground shadow-lg shadow-primary/25 hover:bg-primary/90 transition-all"
              >
                <Globe className="h-4 w-4" />
                Start a Scan
              </a>
            </motion.div>
          ) : viewMode === "grid" ? (
            <motion.div
              key="grid"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="space-y-8"
            >
              {showSubdomains && filteredSubdomains.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-4">
                    <Globe className="h-4 w-4 text-primary" />
                    <h2 className="text-sm font-semibold text-foreground">
                      Subdomains
                    </h2>
                    <span className="rounded-md bg-primary/10 px-1.5 py-0.5 text-xs font-semibold text-primary">
                      {filteredSubdomains.length}
                    </span>
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {filteredSubdomains.map((sub) => (
                      <motion.div
                        key={sub.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="group relative rounded-xl border border-border/50 bg-card/60 p-5 transition-all duration-300 hover:border-primary/30 hover:shadow-lg hover:shadow-primary/5 hover:-translate-y-0.5"
                      >
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex items-center gap-2 min-w-0 flex-1">
                            <FavoriteButton assetType="subdomain" assetId={sub.id} />
                            <span className="font-mono text-sm font-semibold text-foreground truncate">
                              {sub.hostname}
                            </span>
                          </div>
                          <span
                            className={cn(
                              "h-2 w-2 rounded-full flex-shrink-0 mt-1.5",
                              sub.is_alive ? "bg-emerald-400 shadow-sm shadow-emerald-400/50" : "bg-zinc-500"
                            )}
                          />
                        </div>
                        <p className="text-xs text-muted-foreground font-mono mb-3 truncate">
                          {sub.ip_addresses[0] || "No IP detected"}
                        </p>
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Badge
                              variant={sub.is_alive ? "success" : "secondary"}
                              className="text-xs"
                            >
                              {sub.is_alive ? "Alive" : "Unknown"}
                            </Badge>
                            {(sub as any).status && <StatusBadge status={(sub as any).status} />}
                          </div>
                          <span className="flex items-center gap-1 text-xs text-muted-foreground">
                            <Calendar className="h-3 w-3" />
                            {new Date(sub.discovered_at).toLocaleDateString()}
                          </span>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </div>
              )}

              {showPorts && filteredPorts.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-4">
                    <Server className="h-4 w-4 text-cyan-400" />
                    <h2 className="text-sm font-semibold text-foreground">
                      Open Ports
                    </h2>
                    <span className="rounded-md bg-cyan-400/10 px-1.5 py-0.5 text-xs font-semibold text-cyan-400">
                      {filteredPorts.length}
                    </span>
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {filteredPorts.map((port) => (
                      <motion.div
                        key={port.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="group relative rounded-xl border border-border/50 bg-card/60 p-5 transition-all duration-300 hover:border-cyan-400/30 hover:shadow-lg hover:shadow-cyan-400/5 hover:-translate-y-0.5"
                      >
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex items-center gap-2">
                            <FavoriteButton assetType="port" assetId={port.id} />
                            <span className="inline-flex items-center justify-center rounded-lg bg-cyan-400/10 px-2.5 py-1 font-mono text-lg font-bold text-cyan-400">
                              {port.port_number}
                            </span>
                          </div>
                          <span
                            className={cn(
                              "h-2 w-2 rounded-full flex-shrink-0 mt-1.5",
                              port.state === "open"
                                ? "bg-emerald-400 shadow-sm shadow-emerald-400/50"
                                : "bg-amber-400"
                            )}
                          />
                        </div>
                        <p className="text-sm font-medium text-foreground mb-1">
                          {port.service || "Unknown Service"}
                        </p>
                        <p className="text-xs text-muted-foreground font-mono mb-3 truncate">
                          {port.hostname}
                          {port.version ? ` · ${port.version}` : ""}
                        </p>
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Badge
                              variant={
                                port.state === "open" ? "success" : "warning"
                              }
                              className="text-xs"
                            >
                              {port.state}
                            </Badge>
                            {(port as any).status && <StatusBadge status={(port as any).status} />}
                          </div>
                          <span className="text-xs text-muted-foreground">
                            {port.version || "—"}
                          </span>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </div>
              )}

              {showSsl && filteredSsl.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-4">
                    <Lock className="h-4 w-4 text-emerald-400" />
                    <h2 className="text-sm font-semibold text-foreground">
                      SSL Certificates
                    </h2>
                    <span className="rounded-md bg-emerald-400/10 px-1.5 py-0.5 text-xs font-semibold text-emerald-400">
                      {filteredSsl.length}
                    </span>
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {filteredSsl.map((cert) => {
                      const days = getDaysUntil(cert.not_after);
                      const isExpiring =
                        days !== null && days <= 30 && days >= 0;
                      const isExpired = days !== null && days < 0;
                      return (
                        <motion.div
                          key={cert.id}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          className={cn(
                            "group relative rounded-xl border bg-card/60 p-5 transition-all duration-300 hover:-translate-y-0.5",
                            isExpired
                              ? "border-red-500/30 hover:shadow-lg hover:shadow-red-500/5"
                              : isExpiring
                                ? "border-amber-500/30 hover:shadow-lg hover:shadow-amber-500/5"
                                : "border-border/50 hover:border-emerald-400/30 hover:shadow-lg hover:shadow-emerald-400/5"
                          )}
                        >
                          <div className="flex items-start justify-between mb-3">
                            <div className="flex items-center gap-2 min-w-0 flex-1">
                              <FavoriteButton assetType="ssl_certificate" assetId={cert.id} />
                              <span className="font-mono text-sm font-semibold text-foreground truncate">
                                {cert.hostname}
                              </span>
                            </div>
                            {cert.grade && (
                              <span
                                className={cn(
                                  "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-bold",
                                  getGradeColor(cert.grade)
                                )}
                              >
                                {cert.grade}
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground mb-3 truncate">
                            {cert.issuer || "Unknown Issuer"}
                          </p>
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-1.5">
                              {isExpired ? (
                                <Badge variant="destructive" className="text-xs">
                                  Expired
                                </Badge>
                              ) : isExpiring ? (
                                <Badge variant="warning" className="text-xs">
                                  Expiring Soon
                                </Badge>
                              ) : (
                                <Badge variant="success" className="text-xs">
                                  Valid
                                </Badge>
                              )}
                            </div>
                            <span className="text-xs text-muted-foreground">
                              {cert.not_after
                                ? new Date(
                                    cert.not_after
                                  ).toLocaleDateString()
                                : "—"}
                            </span>
                          </div>
                          {cert.not_after && (
                            <div className="mt-3">
                              <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                                <span>Validity</span>
                                <span>
                                  {days !== null
                                    ? isExpired
                                      ? `Expired ${Math.abs(days)}d ago`
                                      : `${days}d remaining`
                                    : "—"}
                                </span>
                              </div>
                              <div className="h-1 rounded-full bg-muted overflow-hidden">
                                <div
                                  className={cn(
                                    "h-full rounded-full transition-all",
                                    isExpired
                                      ? "bg-red-500"
                                      : isExpiring
                                        ? "bg-amber-500"
                                        : "bg-emerald-500"
                                  )}
                                  style={{
                                    width: `${
                                      days !== null
                                        ? Math.max(5, Math.min(100, (days / 365) * 100))
                                        : 50
                                    }%`,
                                  }}
                                />
                              </div>
                            </div>
                          )}
                        </motion.div>
                      );
                    })}
                  </div>
                </div>
              )}

              {showTech && filteredTech.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-4">
                    <Cpu className="h-4 w-4 text-violet-400" />
                    <h2 className="text-sm font-semibold text-foreground">
                      Technologies
                    </h2>
                    <span className="rounded-md bg-violet-400/10 px-1.5 py-0.5 text-xs font-semibold text-violet-400">
                      {filteredTech.length}
                    </span>
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {filteredTech.map((tech) => (
                      <motion.div
                        key={tech.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="group relative rounded-xl border border-border/50 bg-card/60 p-5 transition-all duration-300 hover:border-violet-400/30 hover:shadow-lg hover:shadow-violet-400/5 hover:-translate-y-0.5"
                      >
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex items-center gap-2 min-w-0 flex-1">
                            <FavoriteButton assetType="technology" assetId={tech.id} />
                            <span className="text-sm font-semibold text-foreground truncate">
                              {tech.name}
                            </span>
                          </div>
                          {tech.category && (
                            <Badge variant="outline" className="text-xs flex-shrink-0">
                              {tech.category}
                            </Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground font-mono mb-3 truncate">
                          {tech.hostname}
                          {tech.version ? ` · ${tech.version}` : ""}
                        </p>
                        <div className="space-y-1.5">
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-muted-foreground">
                              Confidence
                            </span>
                            <span className="font-medium text-foreground">
                              {Math.round(tech.confidence * 100)}%
                            </span>
                          </div>
                          <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-violet-500 to-violet-400 transition-all"
                              style={{
                                width: `${Math.round(tech.confidence * 100)}%`,
                              }}
                            />
                          </div>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </div>
              )}
            </motion.div>
          ) : (
            <motion.div
              key="table"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="rounded-xl border border-border/50 bg-card/60 overflow-hidden"
            >
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border/50 bg-muted/30">
                      {[
                        { field: "type" as SortField, label: "Type" },
                        { field: "name" as SortField, label: "Name" },
                        { field: "status" as SortField, label: "Status" },
                        { field: "date" as SortField, label: "Date" },
                      ].map((col) => (
                        <th
                          key={col.field}
                          className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground cursor-pointer select-none hover:text-foreground transition-colors"
                          onClick={() => toggleSort(col.field)}
                        >
                          <span className="flex items-center gap-1.5">
                            {col.label}
                            <SortIcon field={col.field} />
                          </span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sorted.map((row, i) => {
                      const typeIcons = {
                        subdomain: Globe,
                        port: Server,
                        ssl: Lock,
                        tech: Cpu,
                      };
                      const typeColors = {
                        subdomain: "text-primary",
                        port: "text-cyan-400",
                        ssl: "text-emerald-400",
                        tech: "text-violet-400",
                      };
                      const TypeIcon = typeIcons[row.type];
                      return (
                        <tr
                          key={`${row.type}-${i}`}
                          className="border-b border-border/30 last:border-0 hover:bg-muted/20 transition-colors"
                        >
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <TypeIcon
                                className={cn("h-4 w-4", typeColors[row.type])}
                              />
                              <span className="text-xs font-medium capitalize text-muted-foreground">
                                {row.type}
                              </span>
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <span className="text-sm font-medium font-mono text-foreground">
                              {row.name}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <Badge
                              variant={
                                row.status === "Alive" || row.status === "open"
                                  ? "success"
                                  : row.status.startsWith("A")
                                    ? "success"
                                    : "secondary"
                              }
                              className="text-xs"
                            >
                              {row.status}
                            </Badge>
                          </td>
                          <td className="px-4 py-3">
                            <span className="text-xs text-muted-foreground">
                              {new Date(row.date).toLocaleDateString()}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

export default function AssetsPage() {
  return (
    <ProtectedRoute>
      <AssetsContent />
    </ProtectedRoute>
  );
}
