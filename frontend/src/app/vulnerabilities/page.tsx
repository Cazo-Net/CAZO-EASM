"use client";

import { useEffect, useState, useMemo } from "react";
import { listVulnerabilities, getVulnerabilitySummary, listScans } from "@/lib/api";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  Bug,
  AlertTriangle,
  Shield,
  Search,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Copy,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface Vulnerability {
  id: string;
  scan_id: string;
  template_id: string;
  name: string;
  severity: "critical" | "high" | "medium" | "low" | "unknown";
  vuln_type: string | null;
  host: string;
  matched_at: string | null;
  description: string | null;
  reference: string[];
  tags: string[];
  curl_command: string | null;
  extracted_results: string[];
  found_at: string;
}

interface VulnSummary {
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
}

function getSeverityConfig(severity: string) {
  switch (severity) {
    case "critical":
      return {
        color: "text-severity-critical",
        bg: "bg-severity-critical/10",
        badge: "destructive" as const,
        border: "border-severity-critical/20",
        glow: "shadow-severity-critical/10",
      };
    case "high":
      return {
        color: "text-severity-high",
        bg: "bg-severity-high/10",
        badge: "warning" as const,
        border: "border-severity-high/20",
        glow: "shadow-severity-high/10",
      };
    case "medium":
      return {
        color: "text-severity-medium",
        bg: "bg-severity-medium/10",
        badge: "warning" as const,
        border: "border-severity-medium/20",
        glow: "shadow-severity-medium/10",
      };
    case "low":
      return {
        color: "text-severity-low",
        bg: "bg-severity-low/10",
        badge: "success" as const,
        border: "border-severity-low/20",
        glow: "shadow-severity-low/10",
      };
    default:
      return {
        color: "text-muted-foreground",
        bg: "bg-muted/50",
        badge: "secondary" as const,
        border: "border-border/50",
        glow: "",
      };
  }
}

function formatDate(dateStr: string) {
  const d = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const mins = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString();
}

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text);
}

function VulnContent() {
  const [vulnerabilities, setVulnerabilities] = useState<Vulnerability[]>([]);
  const [summary, setSummary] = useState<VulnSummary>({
    total: 0,
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [scanFilter, setScanFilter] = useState<string>("");
  const [scanOptions, setScanOptions] = useState<{ id: string; domain: string }[]>([]);

  useEffect(() => {
    listScans({ limit: 50 }).then(setScanOptions).catch(() => {});
  }, []);

  useEffect(() => {
    Promise.all([listVulnerabilities(scanFilter || undefined), getVulnerabilitySummary(scanFilter || undefined)])
      .then(([vulns, sum]) => {
        setVulnerabilities(vulns);
        setSummary(sum);
      })
      .catch(() => {
        setError("Failed to load vulnerabilities");
      })
      .finally(() => setLoading(false));
  }, [scanFilter]);

  const filteredVulnerabilities = useMemo(() => {
    return vulnerabilities.filter((vuln) => {
      const matchesSeverity =
        severityFilter === "all" || vuln.severity === severityFilter;
      const matchesSearch =
        !searchQuery ||
        vuln.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        vuln.host.toLowerCase().includes(searchQuery.toLowerCase()) ||
        vuln.template_id.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesSeverity && matchesSearch;
    });
  }, [vulnerabilities, severityFilter, searchQuery]);

  const toggleRow = (id: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const summaryCards = [
    {
      label: "Total",
      value: summary.total,
      icon: Bug,
      color: "text-foreground",
      bg: "bg-surface-2",
      border: "",
    },
    {
      label: "Critical",
      value: summary.critical,
      icon: AlertTriangle,
      color: "text-severity-critical",
      bg: "bg-severity-critical/10",
      border: "border-l-severity-critical",
    },
    {
      label: "High",
      value: summary.high,
      icon: AlertTriangle,
      color: "text-severity-high",
      bg: "bg-severity-high/10",
      border: "border-l-severity-high",
    },
    {
      label: "Medium",
      value: summary.medium,
      icon: Shield,
      color: "text-severity-medium",
      bg: "bg-severity-medium/10",
      border: "border-l-severity-medium",
    },
    {
      label: "Low",
      value: summary.low,
      icon: Shield,
      color: "text-severity-low",
      bg: "bg-severity-low/10",
      border: "border-l-severity-low",
    },
  ];

  const severityFilters = [
    { value: "all", label: "All", count: summary.total },
    { value: "critical", label: "Critical", count: summary.critical },
    { value: "high", label: "High", count: summary.high },
    { value: "medium", label: "Medium", count: summary.medium },
    { value: "low", label: "Low", count: summary.low },
  ];

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Card className="glass max-w-md w-full">
          <CardContent className="p-8 text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-destructive/10">
              <AlertTriangle className="h-7 w-7 text-destructive" />
            </div>
            <h2 className="text-lg font-semibold mb-2">Something went wrong</h2>
            <p className="text-sm text-muted-foreground mb-6">{error}</p>
            <Button
              onClick={() => window.location.reload()}
              variant="outline"
              className="gap-2"
            >
              Try Again
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="page-container-lg">
      <div className="py-6 space-y-6">
        <PageHeader
          title="Vulnerabilities"
          description="Security vulnerabilities discovered across your attack surface"
          icon={<Shield className="h-5 w-5" />}
          breadcrumbs={[{ label: "Home", href: "/dashboard" }, { label: "Vulnerabilities" }]}
        />
        {loading ? (
          <>
            <div className="grid grid-cols-5 gap-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-28 rounded-xl skeleton" />
              ))}
            </div>
            <div className="h-10 w-80 rounded-lg skeleton" />
            <div className="h-96 rounded-xl skeleton" />
          </>
        ) : (
          <>
            <div className="grid grid-cols-5 gap-4">
              {summaryCards.map((stat, i) => {
                const Icon = stat.icon;
                return (
                  <motion.div
                    key={stat.label}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.1 }}
                    className={cn(
                      "glass rounded-xl p-4 hover-glow border-l-2",
                      stat.border
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-xs text-muted-foreground">
                          {stat.label}
                        </p>
                        <p className={cn("text-2xl font-bold mt-0.5 font-mono tabular-nums", stat.color)}>
                          {stat.value}
                        </p>
                      </div>
                      <div
                        className={cn(
                          "flex h-10 w-10 items-center justify-center rounded-lg",
                          stat.bg,
                          stat.color
                        )}
                      >
                        <Icon className="h-5 w-5" />
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>

            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <select
                  value={scanFilter}
                  onChange={(e) => setScanFilter(e.target.value)}
                  className="h-9 px-3 rounded-lg bg-muted/50 border border-border/30 text-sm focus:border-brand/40 focus:outline-none appearance-none cursor-pointer"
                >
                  <option value="">All scans</option>
                  {scanOptions.map((s) => (
                    <option key={s.id} value={s.id}>{s.domain}</option>
                  ))}
                </select>
                {severityFilters.map((f) => (
                  <button
                    key={f.value}
                    onClick={() => setSeverityFilter(f.value)}
                    className={cn(
                      "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-all",
                      severityFilter === f.value
                        ? "bg-brand/10 text-brand"
                        : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                    )}
                  >
                    {f.label}
                    {f.count > 0 && (
                      <span
                        className={cn(
                          "text-[10px] px-1.5 py-0.5 rounded-full font-semibold font-mono tabular-nums",
                          severityFilter === f.value
                            ? "bg-brand/20"
                            : "bg-muted"
                        )}
                      >
                        {f.count}
                      </span>
                    )}
                  </button>
                ))}
              </div>

              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search by name, host, or template..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="h-9 pl-9 pr-8 rounded-lg bg-muted/50 border-border/30 text-sm focus:border-brand/40 focus:outline-none transition-colors w-64"
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery("")}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    <span className="sr-only">Clear search</span>
                    ×
                  </button>
                )}
              </div>
            </div>

            {filteredVulnerabilities.length === 0 ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex flex-col items-center justify-center py-20 text-center"
              >
                <div className="relative mb-6">
                  <div className="absolute inset-0 bg-brand/10 rounded-full blur-xl" />
                  <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl bg-muted/50 border border-border/30">
                    <Bug className="h-10 w-10 text-muted-foreground" />
                  </div>
                </div>
                <h3 className="text-lg font-semibold mb-1">
                  {searchQuery || severityFilter !== "all"
                    ? "No matching vulnerabilities"
                    : "No vulnerabilities found"}
                </h3>
                <p className="text-sm text-muted-foreground max-w-sm">
                  {searchQuery || severityFilter !== "all"
                    ? "Try adjusting your filters or search query"
                    : "Run a scan to discover vulnerabilities in your attack surface"}
                </p>
              </motion.div>
            ) : (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="glass rounded-xl overflow-hidden"
              >
                <Table>
                  <TableHeader>
                    <TableRow className="border-border/30 hover:bg-transparent">
                      <TableHead className="text-xs font-semibold w-8" />
                      <TableHead className="text-xs font-semibold">
                        Name
                      </TableHead>
                      <TableHead className="text-xs font-semibold">
                        Severity
                      </TableHead>
                      <TableHead className="text-xs font-semibold">
                        Host
                      </TableHead>
                      <TableHead className="text-xs font-semibold">
                        Type
                      </TableHead>
                      <TableHead className="text-xs font-semibold">
                        Template ID
                      </TableHead>
                      <TableHead className="text-xs font-semibold">
                        Found
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredVulnerabilities.map((vuln, i) => {
                      const config = getSeverityConfig(vuln.severity);
                      const isExpanded = expandedRows.has(vuln.id);
                      return (
                        <AnimatePresence key={vuln.id}>
                          <motion.tr
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ delay: i * 0.02 }}
                            className={cn(
                              "border-border/20 cursor-pointer transition-colors",
                              isExpanded ? "bg-muted/20" : "hover:bg-muted/20"
                            )}
                            onClick={() => toggleRow(vuln.id)}
                          >
                            <TableCell className="w-8 px-2">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  toggleRow(vuln.id);
                                }}
                                className="p-1 rounded hover:bg-muted/50 transition-colors"
                              >
                                {isExpanded ? (
                                  <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
                                ) : (
                                  <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                                )}
                              </button>
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center gap-2.5">
                                <div
                                  className={cn(
                                    "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg",
                                    config.bg
                                  )}
                                >
                                  <Bug
                                    className={cn("h-3.5 w-3.5", config.color)}
                                  />
                                </div>
                                <span className="font-medium text-sm truncate max-w-[280px]">
                                  {vuln.name}
                                </span>
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge
                                variant={config.badge}
                                className="capitalize text-[10px] px-2 py-0"
                              >
                                {vuln.severity}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <span className="text-sm text-muted-foreground font-mono truncate max-w-[200px] block">
                                {vuln.host}
                              </span>
                            </TableCell>
                            <TableCell>
                              <span className="text-xs text-muted-foreground font-mono">
                                {vuln.vuln_type || "—"}
                              </span>
                            </TableCell>
                            <TableCell>
                              <span className="text-xs text-muted-foreground font-mono">
                                {vuln.template_id}
                              </span>
                            </TableCell>
                            <TableCell>
                              <span className="text-xs text-muted-foreground font-mono">
                                {formatDate(vuln.found_at)}
                              </span>
                            </TableCell>
                          </motion.tr>

                          {isExpanded && (
                            <motion.tr
                              initial={{ opacity: 0, height: 0 }}
                              animate={{ opacity: 1, height: "auto" }}
                              exit={{ opacity: 0, height: 0 }}
                              className="border-border/20 bg-muted/10"
                            >
                              <TableCell colSpan={7} className="p-0">
                                <div className="p-5 space-y-4 border-t border-border/20">
                                  {vuln.description && (
                                    <div>
                                      <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                                        Description
                                      </h4>
                                      <p className="text-sm text-foreground/80 leading-relaxed">
                                        {vuln.description}
                                      </p>
                                    </div>
                                  )}

                                  {vuln.reference &&
                                    vuln.reference.length > 0 && (
                                      <div>
                                        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                                          References
                                        </h4>
                                        <div className="flex flex-wrap gap-2">
                                          {vuln.reference.map((ref, idx) => (
                                            <a
                                              key={idx}
                                              href={ref}
                                              target="_blank"
                                              rel="noopener noreferrer"
                                              onClick={(e) => e.stopPropagation()}
                                              className="inline-flex items-center gap-1.5 text-xs text-brand hover:text-brand/80 bg-brand/5 hover:bg-brand/10 px-2.5 py-1 rounded-lg transition-colors"
                                            >
                                              <ExternalLink className="h-3 w-3" />
                                              {(() => {
                                                try {
                                                  return new URL(ref).hostname;
                                                } catch {
                                                  return ref.length > 30 ? ref.slice(0, 30) + "..." : ref;
                                                }
                                              })()}
                                            </a>
                                          ))}
                                        </div>
                                      </div>
                                    )}

                                  {vuln.tags && vuln.tags.length > 0 && (
                                    <div>
                                      <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                                        Tags
                                      </h4>
                                      <div className="flex flex-wrap gap-1.5">
                                        {vuln.tags.map((tag, idx) => (
                                          <Badge
                                            key={idx}
                                            variant="secondary"
                                            className="text-[10px] px-2 py-0"
                                          >
                                            {tag}
                                          </Badge>
                                        ))}
                                      </div>
                                    </div>
                                  )}

                                  {vuln.curl_command && (
                                    <div>
                                      <div className="flex items-center justify-between mb-2">
                                        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                                          cURL Command
                                        </h4>
                                        <button
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            copyToClipboard(
                                              vuln.curl_command!
                                            );
                                          }}
                                          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                                        >
                                          <Copy className="h-3 w-3" />
                                          Copy
                                        </button>
                                      </div>
                                      <pre className="text-xs text-foreground/80 bg-background/50 border border-border/30 rounded-lg p-3 overflow-x-auto font-mono">
                                        {vuln.curl_command}
                                      </pre>
                                    </div>
                                  )}

                                  {vuln.extracted_results &&
                                    vuln.extracted_results.length > 0 && (
                                      <div>
                                        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                                          Extracted Results
                                        </h4>
                                        <ul className="list-disc list-inside space-y-1">
                                          {vuln.extracted_results.map(
                                            (result, idx) => (
                                              <li
                                                key={idx}
                                                className="text-sm text-foreground/80 font-mono"
                                              >
                                                {result}
                                              </li>
                                            )
                                          )}
                                        </ul>
                                      </div>
                                    )}
                                </div>
                              </TableCell>
                            </motion.tr>
                          )}
                        </AnimatePresence>
                      );
                    })}
                  </TableBody>
                </Table>
              </motion.div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default function VulnerabilitiesPage() {
  return (
    <ProtectedRoute>
      <VulnContent />
    </ProtectedRoute>
  );
}
