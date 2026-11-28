"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { useReplay } from "./ReplayProvider";
import { Globe, Lock, Server, Cpu, Shield, Activity, AlertTriangle } from "lucide-react";

function MetricCard({ label, value, icon: Icon, color, delta }: {
  label: string;
  value: number | string;
  icon: any;
  color: string;
  delta?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-border bg-card p-4"
    >
      <div className="flex items-center justify-between mb-2">
        <div className={cn("flex h-8 w-8 items-center justify-center rounded-lg", color)}>
          <Icon className="h-4 w-4" />
        </div>
        {delta !== undefined && delta !== 0 && (
          <span className={cn("text-[10px] font-medium", delta > 0 ? "text-success" : "text-destructive")}>
            {delta > 0 ? "+" : ""}{delta}
          </span>
        )}
      </div>
      <p className="text-2xl font-semibold tabular-nums">{value}</p>
      <p className="text-[10px] text-muted-foreground mt-1">{label}</p>
    </motion.div>
  );
}

export function HistoricalDashboard() {
  const { state } = useReplay();
  const scan = state.selectedScan;
  const prevScan = state.scans[state.scans.findIndex((s) => s.scan_id === scan?.scan_id) - 1];

  const metrics = [
    { label: "Total Assets", value: scan?.total_assets ?? 0, icon: Globe, color: "bg-brand/10 text-brand", delta: prevScan ? (scan?.total_assets ?? 0) - prevScan.total_assets : undefined },
    { label: "Subdomains", value: scan?.total_subdomains ?? 0, icon: Globe, color: "bg-info/10 text-info", delta: prevScan ? (scan?.total_subdomains ?? 0) - prevScan.total_subdomains : undefined },
    { label: "Open Ports", value: scan?.total_ports ?? 0, icon: Server, color: "bg-warning/10 text-warning", delta: prevScan ? (scan?.total_ports ?? 0) - prevScan.total_ports : undefined },
    { label: "Certificates", value: scan?.total_certificates ?? 0, icon: Lock, color: "bg-success/10 text-success", delta: prevScan ? (scan?.total_certificates ?? 0) - prevScan.total_certificates : undefined },
    { label: "Technologies", value: scan?.total_technologies ?? 0, icon: Cpu, color: "bg-accent-2/10 text-accent-2", delta: prevScan ? (scan?.total_technologies ?? 0) - prevScan.total_technologies : undefined },
    { label: "Exposure Score", value: scan?.exposure_score ?? "—", icon: Shield, color: (scan?.exposure_score ?? 0) > 60 ? "bg-destructive/10 text-destructive" : "bg-success/10 text-success", delta: prevScan && scan ? scan.exposure_score - prevScan.exposure_score : undefined },
    { label: "Risk Score", value: scan?.risk_score ?? "—", icon: AlertTriangle, color: (scan?.risk_score ?? 0) > 50 ? "bg-destructive/10 text-destructive" : "bg-success/10 text-success", delta: prevScan && scan ? scan.risk_score - prevScan.risk_score : undefined },
    { label: "Critical Vulns", value: scan?.critical_count ?? 0, icon: AlertTriangle, color: "bg-destructive/10 text-destructive", delta: prevScan ? (scan?.critical_count ?? 0) - prevScan.critical_count : undefined },
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {metrics.map((m) => (
        <MetricCard key={m.label} {...m} />
      ))}
    </div>
  );
}
