"use client";

import { useEffect, useState, useMemo } from "react";
import { listWhoisRecords } from "@/lib/api";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PageHeader } from "@/components/common/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import {
  Search,
  Globe,
  Calendar,
  Server,
  User,
  Building,
  MapPin,
  Loader2,
  ExternalLink,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { format } from "date-fns";
import type { WhoisRecord } from "@/types";

type ViewMode = "cards" | "table";

function getDaysUntil(dateStr: string | null): number | null {
  if (!dateStr) return null;
  const diff = new Date(dateStr).getTime() - Date.now();
  return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

function getExpirationStatus(
  daysLeft: number | null
): "active" | "expiring" | "expired" {
  if (daysLeft === null) return "active";
  if (daysLeft < 0) return "expired";
  if (daysLeft <= 30) return "expiring";
  return "active";
}

function getStatusConfig(status: "active" | "expiring" | "expired") {
  switch (status) {
    case "active":
      return {
        label: "Active",
        variant: "success" as const,
        className:
          "bg-success/10 text-success border-success/30",
      };
    case "expiring":
      return {
        label: "Expiring Soon",
        variant: "warning" as const,
        className:
          "bg-warning/10 text-warning border-warning/30",
      };
    case "expired":
      return {
        label: "Expired",
        variant: "destructive" as const,
        className: "bg-destructive/10 text-destructive border-destructive/30",
      };
  }
}

function WhoisContent() {
  const [records, setRecords] = useState<WhoisRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("cards");

  useEffect(() => {
    listWhoisRecords()
      .then((data) => setRecords(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const q = searchQuery.toLowerCase();
    return records.filter(
      (r) =>
        r.domain.toLowerCase().includes(q) ||
        (r.registrar && r.registrar.toLowerCase().includes(q)) ||
        (r.registrant_name && r.registrant_name.toLowerCase().includes(q)) ||
        (r.registrant_org && r.registrant_org.toLowerCase().includes(q))
    );
  }, [records, searchQuery]);

  const stats = useMemo(
    () => ({
      total: records.length,
      active: records.filter(
        (r) => getExpirationStatus(getDaysUntil(r.expiration_date)) === "active"
      ).length,
      expiring: records.filter(
        (r) =>
          getExpirationStatus(getDaysUntil(r.expiration_date)) === "expiring"
      ).length,
      expired: records.filter(
        (r) =>
          getExpirationStatus(getDaysUntil(r.expiration_date)) === "expired"
      ).length,
    }),
    [records]
  );

  return (
    <div className="page-container-lg">
      <div className="py-6 space-y-6">
        <PageHeader
          title="WHOIS Records"
          description="Domain registration and ownership information discovered across all scans."
          icon={<Globe className="h-5 w-5" />}
          breadcrumbs={[{ label: "Home", href: "/dashboard" }, { label: "WHOIS Records" }]}
          actions={
            <div className="flex items-center gap-1 rounded-lg border border-border/60 bg-surface-2/50 p-1">
              <button
                onClick={() => setViewMode("cards")}
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-md transition-all",
                  viewMode === "cards"
                    ? "bg-card text-foreground shadow"
                    : "text-muted-foreground hover:text-foreground"
                )}
                aria-label="Card view"
              >
                <svg
                  className="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <rect x="3" y="3" width="7" height="7" rx="1" />
                  <rect x="14" y="3" width="7" height="7" rx="1" />
                  <rect x="3" y="14" width="7" height="7" rx="1" />
                  <rect x="14" y="14" width="7" height="7" rx="1" />
                </svg>
              </button>
              <button
                onClick={() => setViewMode("table")}
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-md transition-all",
                  viewMode === "table"
                    ? "bg-card text-foreground shadow"
                    : "text-muted-foreground hover:text-foreground"
                )}
                aria-label="Table view"
              >
                <svg
                  className="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path d="M3 5h18M3 12h18M3 19h18" />
                </svg>
              </button>
            </div>
          }
        />

        <div className="mt-6 space-y-6">
        <div className="grid grid-cols-4 gap-4">
          {[
            {
              label: "Total Records",
              value: stats.total,
              icon: Globe,
              color: "text-foreground",
            },
            {
              label: "Active",
              value: stats.active,
              icon: Globe,
              color: "text-success",
            },
            {
              label: "Expiring Soon",
              value: stats.expiring,
              icon: Calendar,
              color: "text-warning",
            },
            {
              label: "Expired",
              value: stats.expired,
              icon: Calendar,
              color: "text-destructive",
            },
          ].map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              className="glass rounded-xl p-4 hover-glow"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground">{stat.label}</p>
                  <p
                    className={cn("text-2xl font-bold mt-0.5 font-mono tabular-nums", stat.color)}
                  >
                    {stat.value}
                  </p>
                </div>
                <div
                  className={cn(
                    "flex h-10 w-10 items-center justify-center rounded-lg bg-muted/50",
                    stat.color
                  )}
                >
                  <stat.icon className="h-5 w-5" />
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        <div className="relative">
          <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by domain, registrar, registrant name, or organization..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-11 pl-11 bg-muted/30 border-border/50 focus:border-brand/50 focus:ring-brand/20"
          />
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
                <div key={i} className="h-56 rounded-xl skeleton" />
              ))}
            </motion.div>
          ) : filtered.length === 0 ? (
            <motion.div
              key="empty"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="flex flex-col items-center justify-center py-24 text-center"
            >
              <div className="relative mb-6">
                <div className="absolute inset-0 rounded-full bg-brand/20 blur-2xl" />
                <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl border border-border/50 bg-card/80">
                  <Globe className="h-10 w-10 text-muted-foreground" />
                </div>
              </div>
              <h3 className="text-xl font-semibold mb-2">
                {searchQuery
                  ? "No matching WHOIS records"
                  : "No WHOIS records found"}
              </h3>
              <p className="text-sm text-muted-foreground max-w-sm mb-6">
                {searchQuery
                  ? "Try adjusting your search query to find what you're looking for."
                  : "Start a scan to discover WHOIS registration data for your domains."}
              </p>
              {!searchQuery && (
                <a
                  href="/scan/new"
                  className="inline-flex items-center gap-2 rounded-lg gradient-brand px-5 py-2.5 text-sm font-medium text-primary-foreground shadow-glow-sm hover:bg-primary/90 transition-all"
                >
                  <Globe className="h-4 w-4" />
                  Start a Scan
                </a>
              )}
            </motion.div>
          ) : viewMode === "cards" ? (
            <motion.div
              key="cards"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3"
            >
              {filtered.map((record, i) => {
                const daysLeft = getDaysUntil(record.expiration_date);
                const status = getExpirationStatus(daysLeft);
                const statusConfig = getStatusConfig(status);

                return (
                  <motion.div
                    key={record.id}
                    initial={{ opacity: 0, y: 15 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    transition={{ delay: i * 0.03 }}
                    className={cn(
                      "group relative rounded-xl border bg-card/60 p-5 transition-all duration-300 hover:-translate-y-0.5",
                      status === "expired"
                        ? "border-destructive/30 hover:shadow-lg hover:shadow-destructive/5"
                        : status === "expiring"
                          ? "border-warning/30 hover:shadow-lg hover:shadow-warning/5"
                          : "border-border/50 hover:border-brand/30 hover:shadow-lg hover:shadow-brand/5"
                    )}
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand/10 border border-brand/20">
                          <Globe className="h-5 w-5 text-brand" />
                        </div>
                        <div className="min-w-0">
                          <h3 className="font-semibold text-foreground truncate group-hover:text-brand transition-colors">
                            {record.domain}
                          </h3>
                          {record.registrar && (
                            <p className="text-xs text-muted-foreground truncate">
                              {record.registrar}
                            </p>
                          )}
                        </div>
                      </div>
                      <Badge
                        variant={statusConfig.variant}
                        className="text-[10px] px-2 py-0 flex-shrink-0"
                      >
                        {statusConfig.label}
                      </Badge>
                    </div>

                    <div className="space-y-3 mb-4">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Calendar className="h-3.5 w-3.5 flex-shrink-0" />
                        <span className="truncate">
                          Registered:{" "}
                          <span className="text-foreground font-medium">
                            {record.creation_date
                              ? format(
                                  new Date(record.creation_date),
                                  "MMM d, yyyy"
                                )
                              : "—"}
                          </span>
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Calendar className="h-3.5 w-3.5 flex-shrink-0" />
                        <span className="truncate">
                          Expires:{" "}
                          <span
                            className={cn(
                              "font-medium",
                              status === "expired"
                                ? "text-destructive"
                                : status === "expiring"
                                  ? "text-warning"
                                  : "text-foreground"
                            )}
                          >
                            {record.expiration_date
                              ? format(
                                  new Date(record.expiration_date),
                                  "MMM d, yyyy"
                                )
                              : "—"}
                          </span>
                        </span>
                      </div>
                      {daysLeft !== null && (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <span className="ml-5.5 text-xs">
                            {daysLeft < 0 ? (
                              <span className="text-destructive font-medium">
                                Expired {Math.abs(daysLeft)}d ago
                              </span>
                            ) : daysLeft <= 30 ? (
                              <span className="text-warning font-medium">
                                {daysLeft}d remaining
                              </span>
                            ) : (
                              <span className="text-success font-medium">
                                {daysLeft}d remaining
                              </span>
                            )}
                          </span>
                        </div>
                      )}
                    </div>

                    {record.name_servers &&
                      record.name_servers.length > 0 && (
                        <div className="mb-4">
                          <div className="flex items-center gap-1.5 mb-2">
                            <Server className="h-3.5 w-3.5 text-muted-foreground" />
                            <span className="text-xs font-medium text-muted-foreground">
                              Name Servers
                            </span>
                          </div>
                          <div className="flex flex-wrap gap-1.5">
                            {record.name_servers.map((ns) => (
                              <span
                                key={ns}
                                className="inline-flex items-center rounded-md border border-border/50 bg-muted/30 px-2 py-0.5 text-[10px] font-medium text-muted-foreground font-mono"
                              >
                                {ns}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                    {(record.registrant_name ||
                      record.registrant_org ||
                      record.registrant_country) && (
                      <div className="border-t border-border/30 pt-3">
                        <div className="flex items-center gap-1.5 mb-2">
                          <User className="h-3.5 w-3.5 text-muted-foreground" />
                          <span className="text-xs font-medium text-muted-foreground">
                            Registrant
                          </span>
                        </div>
                        <div className="space-y-1">
                          {record.registrant_name && (
                            <div className="flex items-center gap-2 text-xs">
                              <User className="h-3 w-3 text-muted-foreground/60 flex-shrink-0" />
                              <span className="text-foreground truncate">
                                {record.registrant_name}
                              </span>
                            </div>
                          )}
                          {record.registrant_org && (
                            <div className="flex items-center gap-2 text-xs">
                              <Building className="h-3 w-3 text-muted-foreground/60 flex-shrink-0" />
                              <span className="text-muted-foreground truncate">
                                {record.registrant_org}
                              </span>
                            </div>
                          )}
                          {record.registrant_country && (
                            <div className="flex items-center gap-2 text-xs">
                              <MapPin className="h-3 w-3 text-muted-foreground/60 flex-shrink-0" />
                              <span className="text-muted-foreground">
                                {record.registrant_country}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    <div className="flex items-center justify-between mt-4 pt-3 border-t border-border/30">
                      <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
                        <Calendar className="h-3 w-3" />
                        Scanned:{" "}
                        {format(
                          new Date(record.scanned_at),
                          "MMM d, yyyy"
                        )}
                      </span>
                    </div>
                  </motion.div>
                );
              })}
            </motion.div>
          ) : (
            <motion.div
              key="table"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="glass rounded-xl overflow-hidden"
            >
              <Table>
                <TableHeader>
                  <TableRow className="border-border/30 hover:bg-transparent">
                    <TableHead className="text-xs font-semibold">
                      Domain
                    </TableHead>
                    <TableHead className="text-xs font-semibold">
                      Registrar
                    </TableHead>
                    <TableHead className="text-xs font-semibold">
                      Created
                    </TableHead>
                    <TableHead className="text-xs font-semibold">
                      Expires
                    </TableHead>
                    <TableHead className="text-xs font-semibold">
                      Status
                    </TableHead>
                    <TableHead className="text-xs font-semibold">
                      Name Servers
                    </TableHead>
                    <TableHead className="text-xs font-semibold">
                      Registrant
                    </TableHead>
                    <TableHead className="text-xs font-semibold">
                      Scanned
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((record) => {
                    const daysLeft = getDaysUntil(record.expiration_date);
                    const status = getExpirationStatus(daysLeft);
                    const statusConfig = getStatusConfig(status);

                    return (
                      <TableRow
                        key={record.id}
                        className="border-border/20 hover:bg-muted/20"
                      >
                        <TableCell>
                          <div className="flex items-center gap-2.5">
                            <Globe className="h-4 w-4 text-brand shrink-0" />
                            <span className="font-medium font-mono text-sm">
                              {record.domain}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <span className="text-sm text-muted-foreground">
                            {record.registrar || "—"}
                          </span>
                        </TableCell>
                        <TableCell>
                          <span className="text-xs text-muted-foreground font-mono">
                            {record.creation_date
                              ? format(
                                  new Date(record.creation_date),
                                  "MMM d, yyyy"
                                )
                              : "—"}
                          </span>
                        </TableCell>
                        <TableCell>
                          <span
                            className={cn(
                              "text-xs font-mono",
                              status === "expired"
                                ? "text-destructive"
                                : status === "expiring"
                                  ? "text-warning"
                                  : "text-muted-foreground"
                            )}
                          >
                            {record.expiration_date
                              ? format(
                                  new Date(record.expiration_date),
                                  "MMM d, yyyy"
                                )
                              : "—"}
                          </span>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={statusConfig.variant}
                            className="text-[10px] px-2 py-0"
                          >
                            {statusConfig.label}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1 max-w-[200px]">
                            {record.name_servers.slice(0, 2).map((ns) => (
                              <span
                                key={ns}
                                className="inline-flex items-center rounded border border-border/50 bg-muted/30 px-1.5 py-0.5 text-[9px] font-mono text-muted-foreground"
                              >
                                {ns.length > 16 ? ns.slice(0, 16) + "…" : ns}
                              </span>
                            ))}
                            {record.name_servers.length > 2 && (
                              <span className="text-[9px] text-muted-foreground">
                                +{record.name_servers.length - 2}
                              </span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="text-xs">
                            {record.registrant_name && (
                              <p className="text-foreground font-medium truncate max-w-[150px]">
                                {record.registrant_name}
                              </p>
                            )}
                            {record.registrant_org && (
                              <p className="text-muted-foreground truncate max-w-[150px]">
                                {record.registrant_org}
                              </p>
                            )}
                            {!record.registrant_name &&
                              !record.registrant_org && (
                                <span className="text-muted-foreground">
                                  —
                                </span>
                              )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <span className="text-xs text-muted-foreground font-mono">
                            {format(
                              new Date(record.scanned_at),
                              "MMM d, yyyy"
                            )}
                          </span>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      </div>
    </div>
  );
}

export default function WhoisPage() {
  return (
    <ProtectedRoute>
      <WhoisContent />
    </ProtectedRoute>
  );
}
