"use client";

import { useEffect, useState } from "react";
import {
  FileText,
  Download,
  Trash2,
  Plus,
  Calendar,
  HardDrive,
  FileJson,
  FileImage,
  FileCode,
  FileSpreadsheet,
  X,
  Loader2,
  BarChart3,
  Clock,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PageHeader } from "@/components/common/PageHeader";
import { StatCard } from "@/components/common/StatCard";
import { cn } from "@/lib/utils";

interface Report {
  id: string;
  scan_id: string;
  format: string;
  file_size: number | null;
  generated_at: string;
}

interface Scan {
  id: string;
  domain: string;
  status: string;
  created_at: string;
}

const formatIcons: Record<string, React.ElementType> = {
  json: FileJson,
  pdf: FileImage,
  html: FileCode,
  csv: FileSpreadsheet,
};

const formatColors: Record<string, string> = {
  json: "bg-brand/10 text-brand border-brand/30",
  pdf: "bg-destructive/10 text-destructive border-destructive/30",
  html: "bg-warning/10 text-warning border-warning/30",
  csv: "bg-success/10 text-success border-success/30",
};

function ReportsContent() {
  const [reports, setReports] = useState<Report[]>([]);
  const [scans, setScans] = useState<Scan[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedScan, setSelectedScan] = useState("");
  const [selectedFormat, setSelectedFormat] = useState("json");

  useEffect(() => {
    fetchReports();
    fetchScans();
  }, []);

  const fetchReports = async () => {
    try {
      const response = await api.get("/reports");
      setReports(response.data);
    } catch (error) {
      console.error("Failed to fetch reports:", error);
    } finally {
      setLoading(false);
    }
  };

  const fetchScans = async () => {
    try {
      const response = await api.get("/scans", { params: { limit: 50 } });
      setScans(response.data);
    } catch (error) {
      console.error("Failed to fetch scans:", error);
    }
  };

  const handleDownload = async (reportId: string, format: string) => {
    try {
      const response = await api.get(`/reports/${reportId}/download`, {
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `attacksec-report.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Failed to download report:", error);
    }
  };

  const handleDelete = async (reportId: string) => {
    try {
      await api.delete(`/reports/${reportId}`);
      setReports(reports.filter((r) => r.id !== reportId));
    } catch (error) {
      console.error("Failed to delete report:", error);
    }
  };

  const handleGenerate = async () => {
    if (!selectedScan) return;
    setGenerating(true);
    try {
      await api.post("/reports", null, {
        params: { scan_id: selectedScan, format: selectedFormat },
      });
      await fetchReports();
      setDialogOpen(false);
      setSelectedScan("");
      setSelectedFormat("json");
    } catch (error) {
      console.error("Failed to generate report:", error);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="page-container-md">
      <div className="py-6">
        <PageHeader
          title="Reports"
          description="Generated scan reports and exports."
          icon={<FileText className="h-5 w-5" />}
          breadcrumbs={[{ label: "Home", href: "/dashboard" }, { label: "Reports" }]}
          actions={
            <Button onClick={() => setDialogOpen(true)} className="gradient-brand text-white shadow-elevation-2">
              <Plus className="h-4 w-4" />
              Generate Report
            </Button>
          }
        />

        {/* Summary Stats */}
        <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Total Reports"
            value={loading ? "—" : reports.length}
            icon={<FileText className="h-5 w-5" />}
            accent="brand"
            hint={`${new Set(reports.map(r => r.scan_id)).size} scans covered`}
          />
          <StatCard
            label="Total Size"
            value={loading ? "—" : `${(reports.reduce((acc, r) => acc + (r.file_size || 0), 0) / 1024).toFixed(1)} KB`}
            icon={<HardDrive className="h-5 w-5" />}
            accent="info"
            hint="across all formats"
          />
          <StatCard
            label="Formats"
            value={loading ? "—" : Array.from(new Set(reports.map(r => r.format))).length}
            icon={<BarChart3 className="h-5 w-5" />}
            accent="violet"
            hint={reports.length > 0 ? Array.from(new Set(reports.map(r => r.format))).join(", ") : "none"}
          />
          <StatCard
            label="Latest Report"
            value={loading ? "—" : reports.length > 0 ? new Date(reports.sort((a, b) => new Date(b.generated_at).getTime() - new Date(a.generated_at).getTime())[0].generated_at).toLocaleDateString() : "—"}
            icon={<Clock className="h-5 w-5" />}
            accent="success"
            hint={reports.length > 0 ? "last generated" : "no reports yet"}
          />
        </div>

        <div className="mt-6">
        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-48 rounded-xl skeleton" />
            ))}
          </div>
        ) : reports.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col items-center justify-center py-24 text-center"
          >
            <div className="relative mb-6">
              <div className="absolute inset-0 rounded-full bg-brand/20 blur-2xl" />
              <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl border border-border/50 bg-card/80">
                <FileText className="h-10 w-10 text-muted-foreground" />
              </div>
            </div>
            <h3 className="text-xl font-semibold mb-2">
              No reports generated yet
            </h3>
            <p className="text-sm text-muted-foreground max-w-sm mb-6">
              Run a scan first, then generate a report from the scan results to
              export your attack surface data.
            </p>
            <button
              onClick={() => setDialogOpen(true)}
              className="inline-flex items-center gap-2 rounded-lg gradient-brand px-5 py-2.5 text-sm font-medium text-white shadow-lg shadow-primary/25 hover:bg-primary/90 transition-all"
            >
              <Plus className="h-4 w-4" />
              Generate Your First Report
            </button>
          </motion.div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <AnimatePresence>
              {reports.map((report, i) => {
                const FormatIcon =
                  formatIcons[report.format] || FileText;
                return (
                  <motion.div
                    key={report.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    transition={{ delay: i * 0.05 }}
                    className="group relative rounded-xl border border-border/50 bg-card/60 p-5 transition-all duration-300 hover:border-brand/30 hover:shadow-lg hover:shadow-brand/5 hover:-translate-y-0.5"
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <div
                          className={cn(
                            "flex h-10 w-10 items-center justify-center rounded-lg border",
                            formatColors[report.format] ||
                              "bg-muted text-muted-foreground"
                          )}
                        >
                          <FormatIcon className="h-5 w-5" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-foreground font-mono">
                            {report.id.slice(0, 8)}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            Scan: {report.scan_id.slice(0, 8)}...
                          </p>
                        </div>
                      </div>
                      <Badge
                        variant="outline"
                        className="uppercase text-xs font-bold"
                      >
                        {report.format}
                      </Badge>
                    </div>

                    <div className="flex items-center gap-4 text-xs text-muted-foreground mb-4">
                      <span className="flex items-center gap-1">
                        <HardDrive className="h-3 w-3" />
                        {report.file_size
                          ? `${(report.file_size / 1024).toFixed(1)} KB`
                          : "—"}
                      </span>
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        {new Date(report.generated_at).toLocaleDateString()}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        onClick={() => handleDownload(report.id, report.format)}
                        className="flex-1 gradient-brand text-white shadow shadow-primary/20"
                      >
                        <Download className="h-3.5 w-3.5" />
                        Download
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleDelete(report.id)}
                        className="text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
        )}
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md border-border/50 bg-card/95 backdrop-blur-xl">
          <DialogHeader>
            <DialogTitle>Generate Report</DialogTitle>
            <DialogDescription>
              Select a scan and format to generate a new report.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">Select Scan</label>
              <select
                value={selectedScan}
                onChange={(e) => setSelectedScan(e.target.value)}
                className="flex h-10 w-full rounded-lg border border-border/50 bg-muted/30 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-brand/30 focus:border-brand/50"
              >
                <option value="">Choose a scan...</option>
                {scans
                  .filter((s) => s.status === "completed")
                  .map((scan) => (
                    <option key={scan.id} value={scan.id}>
                      {scan.domain} — {new Date(
                        scan.created_at
                      ).toLocaleDateString()}
                    </option>
                  ))}
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Report Format</label>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { value: "json", label: "JSON", icon: FileJson },
                  { value: "pdf", label: "PDF", icon: FileImage },
                  { value: "html", label: "HTML", icon: FileCode },
                  { value: "csv", label: "CSV", icon: FileSpreadsheet },
                ].map((fmt) => {
                  const FIcon = fmt.icon;
                  return (
                    <button
                      key={fmt.value}
                      onClick={() => setSelectedFormat(fmt.value)}
                      className={cn(
                        "flex items-center gap-2 rounded-lg border p-3 text-sm font-medium transition-all",
                        selectedFormat === fmt.value
                          ? "border-brand/50 bg-brand/10 text-brand"
                          : "border-border/50 bg-muted/30 text-muted-foreground hover:border-border hover:text-foreground"
                      )}
                    >
                      <FIcon className="h-4 w-4" />
                      {fmt.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => setDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleGenerate}
              disabled={!selectedScan || generating}
              className="gradient-brand"
            >
              {generating ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              Generate
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      </div>
    </div>
  );
}

export default function ReportsPage() {
  return (
    <ProtectedRoute>
      <ReportsContent />
    </ProtectedRoute>
  );
}
