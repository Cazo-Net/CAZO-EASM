"use client";

import Link from "next/link";
import {
  ArrowRight,
  Clock,
  CheckCircle,
  Loader2,
  XCircle,
  Globe,
  Shield,
  Zap,
  SlidersHorizontal,
  Trash2,
} from "lucide-react";
import { motion } from "framer-motion";
import type { Scan } from "@/types";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface ScanHistoryProps {
  scans: Scan[];
  loading?: boolean;
  onDelete?: (scan: Scan) => void;
}

function getStatusConfig(status: Scan["status"]) {
  switch (status) {
    case "completed":
      return { icon: CheckCircle, color: "text-emerald-500", bg: "bg-emerald-500/10", badge: "success" as const };
    case "running":
      return { icon: Loader2, color: "text-blue-500", bg: "bg-blue-500/10", badge: "info" as const };
    case "failed":
      return { icon: XCircle, color: "text-red-500", bg: "bg-red-500/10", badge: "destructive" as const };
    default:
      return { icon: Clock, color: "text-muted-foreground", bg: "bg-muted", badge: "secondary" as const };
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

export function ScanHistory({ scans, loading, onDelete }: ScanHistoryProps) {
  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-20 rounded-xl skeleton"
          />
        ))}
      </div>
    );
  }

  if (scans.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-muted/50 mb-3">
          <Globe className="h-7 w-7 text-muted-foreground" />
        </div>
        <p className="text-sm text-muted-foreground">
          No scans yet. Start your first scan to begin.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {scans.map((scan, i) => {
        const config = getStatusConfig(scan.status);
        const Icon = config.icon;
        const ScanTypeIcon = getScanTypeIcon(scan.scan_type);

        return (
          <motion.div
            key={scan.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
          >
            <Link
              href={`/scan/${scan.id}`}
              className="group flex items-center justify-between rounded-xl border border-border p-4 transition-all hover:border-primary/20 hover:bg-muted/20 hover:shadow-sm"
            >
              <div className="flex items-center gap-3">
                <div className={cn("flex h-10 w-10 items-center justify-center rounded-xl", config.bg)}>
                  <Icon className={cn("h-5 w-5", config.color, scan.status === "running" && "animate-spin")} />
                </div>
                <div className="min-w-0">
                  <p className="font-medium group-hover:text-primary transition-colors truncate">
                    {scan.domain}
                  </p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-xs text-muted-foreground">
                      {formatDate(scan.created_at)}
                    </span>
                    <span className="text-[10px] text-muted-foreground bg-muted/50 px-1.5 py-0 rounded-full flex items-center gap-1">
                      <ScanTypeIcon className="h-2.5 w-2.5" />
                      {scan.scan_type}
                    </span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <Badge variant={config.badge} className="capitalize text-[10px] px-2 py-0">
                    {scan.status}
                  </Badge>
                  {scan.status === "running" && scan.progress > 0 && (
                    <div className="mt-1.5 w-20">
                      <Progress value={scan.progress} className="h-1" />
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  {onDelete && (
                    <button
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        onDelete(scan);
                      }}
                      className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-all"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                  <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all" />
                </div>
              </div>
            </Link>
          </motion.div>
        );
      })}
    </div>
  );
}
