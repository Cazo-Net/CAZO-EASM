"use client";

import { cn } from "@/lib/utils";
import {
  Activity,
  Moon,
  Archive,
  Trash2,
} from "lucide-react";

export type AssetStatus = "active" | "dormant" | "decommissioned" | "archived";

const statusConfig: Record<AssetStatus, { label: string; icon: any; color: string; bg: string }> = {
  active: { label: "Active", icon: Activity, color: "text-emerald-400", bg: "bg-emerald-500/10" },
  dormant: { label: "Dormant", icon: Moon, color: "text-amber-400", bg: "bg-amber-500/10" },
  decommissioned: { label: "Decommissioned", icon: Trash2, color: "text-red-400", bg: "bg-red-500/10" },
  archived: { label: "Archived", icon: Archive, color: "text-muted-foreground", bg: "bg-muted/50" },
};

interface StatusBadgeProps {
  status: string;
  size?: "sm" | "md";
}

export function StatusBadge({ status, size = "sm" }: StatusBadgeProps) {
  const config = statusConfig[status as AssetStatus] || statusConfig.active;
  const Icon = config.icon;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full font-medium",
        config.color,
        config.bg,
        size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs"
      )}
    >
      <Icon className={size === "sm" ? "h-2.5 w-2.5" : "h-3 w-3"} />
      {config.label}
    </span>
  );
}

export function StatusSelect({
  value,
  onChange,
}: {
  value: string;
  onChange: (status: string) => void;
}) {
  return (
    <div className="flex gap-1.5">
      {(Object.entries(statusConfig) as [AssetStatus, typeof statusConfig[AssetStatus]][]).map(
        ([key, config]) => {
          const Icon = config.icon;
          return (
            <button
              key={key}
              onClick={() => onChange(key)}
              className={cn(
                "flex items-center gap-1 rounded-lg border px-2 py-1 text-xs transition-all",
                value === key
                  ? `${config.bg} ${config.color} border-current/20`
                  : "border-border/50 text-muted-foreground hover:bg-muted/30"
              )}
            >
              <Icon className="h-3 w-3" />
              {config.label}
            </button>
          );
        }
      )}
    </div>
  );
}
