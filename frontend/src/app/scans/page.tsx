"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  Plus,
  Search,
  LayoutGrid,
  Table as TableIcon,
  Trash2,
  ArrowRight,
  ScanSearch,
  Globe,
  Shield,
  Zap,
  SlidersHorizontal,
  CheckCircle,
  XCircle,
  Loader2,
  Clock,
  AlertTriangle,
  Activity,
  X,
} from "lucide-react";
import { listScans, deleteScan } from "@/lib/api";
import type { Scan } from "@/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PageHeader } from "@/components/common/PageHeader";
import { StatCard } from "@/components/common/StatCard";
import { StatusDot } from "@/components/common/StatusDot";

type ViewMode = "grid" | "table";
type StatusFilter = "all" | "running" | "completed" | "failed" | "pending";

function getStatusConfig(status: Scan["status"]) {
  switch (status) {
    case "completed":
      return { icon: CheckCircle, color: "text-success", bg: "bg-success/10", badge: "success" as const, tone: "success" as const };
    case "running":
      return { icon: Loader2, color: "text-brand", bg: "bg-brand/10", badge: "info" as const, tone: "active" as const };
    case "failed":
      return { icon: XCircle, color: "text-destructive", bg: "bg-destructive/10", badge: "destructive" as const, tone: "danger" as const };
    default:
      return { icon: Clock, color: "text-muted-foreground", bg: "bg-muted", badge: "secondary" as const, tone: "muted" as const };
  }
}

function getScanTypeIcon(type: string) {
  if (type.includes("quick")) return Zap;
  if (type.includes("custom")) return SlidersHorizontal;
  return Shield;
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

function ScansContent() {
  const [scans, setScans] = useState<Scan[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [deleteDialog, setDeleteDialog] = useState<Scan | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listScans({ limit: 100 })
      .then(setScans)
      .catch(() => setError("Failed to load scans"))
      .finally(() => setLoading(false));
  }, []);

  // Poll for updates when there are running scans
  useEffect(() => {
    const hasRunning = scans.some((s) => s.status === "running" || s.status === "pending");
    if (!hasRunning) return;
    const interval = setInterval(() => {
      listScans({ limit: 100 })
        .then(setScans)
        .catch(() => {}); // silent — already showing stale data
    }, 5000);
    return () => clearInterval(interval);
  }, [scans]);

  const filteredScans = useMemo(() => {
    return scans.filter((scan) => {
      const matchesStatus = statusFilter === "all" || scan.status === statusFilter;
      const matchesSearch =
        !searchQuery ||
        scan.domain.toLowerCase().includes(searchQuery.toLowerCase()) ||
        scan.scan_type.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesStatus && matchesSearch;
    });
  }, [scans, statusFilter, searchQuery]);

  const stats = useMemo(() => ({
    total: scans.length,
    running: scans.filter((s) => s.status === "running").length,
    completed: scans.filter((s) => s.status === "completed").length,
    failed: scans.filter((s) => s.status === "failed").length,
  }), [scans]);

  const handleDelete = async () => {
    if (!deleteDialog) return;
    setDeleting(true);
    try {
      await deleteScan(deleteDialog.id);
      setScans((prev) => prev.filter((s) => s.id !== deleteDialog.id));
      setDeleteDialog(null);
    } catch {
      setError("Failed to delete scan");
    } finally {
      setDeleting(false);
    }
  };

  const statusFilters: { value: StatusFilter; label: string; count: number }[] = [
    { value: "all", label: "All", count: stats.total },
    { value: "running", label: "Running", count: stats.running },
    { value: "completed", label: "Completed", count: stats.completed },
    { value: "failed", label: "Failed", count: stats.failed },
  ];

  return (
    <div className="page-container-lg">
      <div className="py-6 space-y-6">
        <PageHeader
          title="Scans"
          description="Manage your attack surface scans"
          icon={<ScanSearch className="h-5 w-5" />}
          breadcrumbs={[{ label: "Home", href: "/dashboard" }, { label: "Scans" }]}
          actions={
            <Link href="/scan/new">
              <Button className="gap-2 gradient-brand text-void shadow-elevation-2 px-5">
                <Plus className="h-4 w-4" />
                New Scan
              </Button>
            </Link>
          }
        />

        {/* Stats */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard label="Total Scans" value={stats.total} icon={<Activity className="h-5 w-5" />} accent="brand" />
          <StatCard label="Running" value={stats.running} icon={<Loader2 className="h-5 w-5" />} accent="info" hint={stats.running > 0 ? "in progress" : "idle"} />
          <StatCard label="Completed" value={stats.completed} icon={<CheckCircle className="h-5 w-5" />} accent="success" />
          <StatCard label="Failed" value={stats.failed} icon={<XCircle className="h-5 w-5" />} accent="danger" hint={stats.failed > 0 ? "needs attention" : "all clear"} />
        </div>

        {error && (
          <div className="text-sm text-destructive bg-destructive/10 rounded-lg px-4 py-2 text-center">
            {error}
          </div>
        )}

        {/* Filters */}
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            {statusFilters.map((f) => (
              <button
                key={f.value}
                onClick={() => setStatusFilter(f.value)}
                className={cn(
                  "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-all",
                  statusFilter === f.value
                    ? "bg-brand/10 text-brand"
                    : "text-muted-foreground hover:text-foreground hover:bg-surface-2/60"
                )}
              >
                {f.label}
                {f.count > 0 && (
                  <span className={cn(
                    "text-[10px] px-1.5 py-0.5 rounded-full font-semibold font-mono tabular-nums",
                    statusFilter === f.value ? "bg-brand/20" : "bg-muted"
                  )}>
                    {f.count}
                  </span>
                )}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                placeholder="Search scans..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-9 pl-9 pr-8 rounded-lg bg-surface-2/50 border border-border/60 text-sm focus:border-brand/40 focus:outline-none transition-colors w-56"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>

            <div className="flex items-center rounded-lg border border-border/60 bg-surface-2/50 p-0.5">
              <button
                onClick={() => setViewMode("grid")}
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-md transition-all",
                  viewMode === "grid" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                )}
              >
                <LayoutGrid className="h-4 w-4" />
              </button>
              <button
                onClick={() => setViewMode("table")}
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-md transition-all",
                  viewMode === "table" ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                )}
              >
                <TableIcon className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Content */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="h-44 rounded-xl skeleton" />
            ))}
          </div>
        ) : filteredScans.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col items-center justify-center py-20 text-center"
          >
            <div className="relative mb-6">
              <div className="absolute inset-0 bg-brand/10 rounded-full blur-xl" />
              <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl bg-surface-2/60 border border-border/30">
                <Globe className="h-10 w-10 text-muted-foreground" />
              </div>
            </div>
            <h3 className="text-lg font-semibold mb-1">
              {searchQuery || statusFilter !== "all" ? "No matching scans" : "No scans yet"}
            </h3>
            <p className="text-sm text-muted-foreground max-w-sm mb-6">
              {searchQuery || statusFilter !== "all"
                ? "Try adjusting your filters or search query"
                : "Start your first attack surface scan to discover vulnerabilities"}
            </p>
            {!searchQuery && statusFilter === "all" && (
              <Link href="/scan/new">
                <Button className="gap-2 gradient-brand text-void">
                  <Plus className="h-4 w-4" />
                  Start First Scan
                </Button>
              </Link>
            )}
          </motion.div>
        ) : viewMode === "grid" ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <AnimatePresence>
              {filteredScans.map((scan, i) => {
                const config = getStatusConfig(scan.status);
                const Icon = config.icon;
                const ScanTypeIcon = getScanTypeIcon(scan.scan_type);
                return (
                  <motion.div
                    key={scan.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    transition={{ delay: i * 0.05 }}
                  >
                    <Link href={`/scan/${scan.id}`} className="block">
                      <div className="group glass rounded-xl p-5 transition-all duration-300 hover-glow hover:-translate-y-0.5 cursor-pointer h-full">
                        <div className="flex items-start justify-between mb-4">
                          <div className="flex items-center gap-3 min-w-0">
                            <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-xl", config.bg)}>
                              <Icon className={cn("h-5 w-5", config.color, scan.status === "running" && "animate-spin")} />
                            </div>
                            <div className="min-w-0">
                              <p className="font-semibold truncate group-hover:text-primary transition-colors font-mono">
                                {scan.domain}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                {formatDate(scan.created_at)}
                              </p>
                            </div>
                          </div>
                          <button
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              setDeleteDialog(scan);
                            }}
                            className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-all"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>

                        <div className="flex items-center gap-2 mb-3">
                          <Badge variant={config.badge} className="capitalize text-[10px] px-2 py-0">
                            {scan.status}
                          </Badge>
                          <div className="flex items-center gap-1 text-[10px] text-muted-foreground bg-muted/50 px-2 py-0.5 rounded-full">
                            <ScanTypeIcon className="h-3 w-3" />
                            {scan.scan_type}
                          </div>
                        </div>

                        {scan.status === "running" && (
                          <div className="space-y-1.5">
                            <Progress
                              value={scan.progress}
                              className="h-1.5"
                              indicatorClassName="bg-gradient-to-r from-brand to-[hsl(var(--brand-2))]"
                            />
                            <p className="text-[10px] text-muted-foreground text-right">
                              {scan.progress}%
                            </p>
                          </div>
                        )}

                        <div className="flex items-center justify-end mt-3">
                          <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 group-hover:translate-x-1 transition-all" />
                        </div>
                      </div>
                    </Link>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="glass rounded-xl overflow-hidden"
          >
            <Table>
              <TableHeader>
                <TableRow className="border-border/30 hover:bg-transparent">
                  <TableHead className="text-xs font-semibold">Domain</TableHead>
                  <TableHead className="text-xs font-semibold">Type</TableHead>
                  <TableHead className="text-xs font-semibold">Status</TableHead>
                  <TableHead className="text-xs font-semibold">Progress</TableHead>
                  <TableHead className="text-xs font-semibold">Created</TableHead>
                  <TableHead className="text-xs font-semibold w-10"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredScans.map((scan) => {
                  const config = getStatusConfig(scan.status);
                  const ScanTypeIcon = getScanTypeIcon(scan.scan_type);
                  return (
                    <TableRow key={scan.id} className="border-border/20 hover:bg-muted/20 cursor-pointer">
                      <Link href={`/scan/${scan.id}`} className="contents">
                        <TableCell>
                          <div className="flex items-center gap-2.5">
                            <Globe className="h-4 w-4 text-muted-foreground shrink-0" />
                            <span className="font-medium font-mono">{scan.domain}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-mono">
                            <ScanTypeIcon className="h-3.5 w-3.5" />
                            {scan.scan_type}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant={config.badge} className="capitalize text-[10px] px-2 py-0">
                            {scan.status}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {scan.status === "running" ? (
                            <div className="flex items-center gap-2 w-24">
                              <Progress value={scan.progress} className="h-1.5 flex-1" />
                              <span className="text-[10px] text-muted-foreground w-7 text-right">{scan.progress}%</span>
                            </div>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground font-mono">
                          {formatDate(scan.created_at)}
                        </TableCell>
                      </Link>
                      <TableCell>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeleteDialog(scan);
                          }}
                          className="p-1.5 rounded-lg hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-all"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </motion.div>
        )}
      </div>

      {/* Delete Dialog */}
      <Dialog open={!!deleteDialog} onOpenChange={() => setDeleteDialog(null)}>
        <DialogContent className="glass-strong">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              Delete Scan
            </DialogTitle>
            <DialogDescription>
              Are you sure you want to delete the scan for{" "}
              <span className="font-semibold text-foreground">{deleteDialog?.domain}</span>?
              This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-3 mt-4">
            <Button variant="outline" onClick={() => setDeleteDialog(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleting}
              className="gap-2"
            >
              {deleting && <Loader2 className="h-4 w-4 animate-spin" />}
              Delete
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function ScansPage() {
  return (
    <ProtectedRoute>
      <ScansContent />
    </ProtectedRoute>
  );
}
