"use client";

import { useEffect, useState } from "react";
import {
  History,
  Plus,
  Pencil,
  Trash2,
  Tag,
  Star,
  LogIn,
  LogOut,
  Scan,
  Shield,
  Loader2,
  Filter,
} from "lucide-react";
import { listAuditLogs } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { AuditLog } from "@/types";

const actionConfig: Record<string, { label: string; icon: any; color: string }> = {
  create: { label: "Created", icon: Plus, color: "text-emerald-400" },
  update: { label: "Updated", icon: Pencil, color: "text-blue-400" },
  delete: { label: "Deleted", icon: Trash2, color: "text-red-400" },
  add_tag: { label: "Tag Added", icon: Tag, color: "text-violet-400" },
  remove_tag: { label: "Tag Removed", icon: Tag, color: "text-muted-foreground" },
  add_favorite: { label: "Favorited", icon: Star, color: "text-amber-400" },
  remove_favorite: { label: "Unfavorited", icon: Star, color: "text-muted-foreground" },
  login: { label: "Login", icon: LogIn, color: "text-cyan-400" },
  logout: { label: "Logout", icon: LogOut, color: "text-muted-foreground" },
  scan: { label: "Scan", icon: Scan, color: "text-primary" },
};

function timeAgo(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
  if (seconds < 60) return "Just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export function AuditLogViewer() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState<string>("");
  const [entityFilter, setEntityFilter] = useState<string>("");

  useEffect(() => {
    loadLogs();
  }, [actionFilter, entityFilter]);

  const loadLogs = async () => {
    setLoading(true);
    try {
      const data = await listAuditLogs({
        action: actionFilter || undefined,
        entity_type: entityFilter || undefined,
        limit: 50,
      });
      setLogs(data);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  };

  const actions = ["create", "update", "delete", "login", "add_tag", "remove_tag", "add_favorite"];
  const entities = ["scan", "organization", "project", "tag", "user", "api_key", "report"];

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <Filter className="h-3 w-3" /> Filter:
        </div>
        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="rounded-lg border border-border bg-muted/30 px-2 py-1 text-xs"
        >
          <option value="">All actions</option>
          {actions.map((a) => (
            <option key={a} value={a}>{actionConfig[a]?.label || a}</option>
          ))}
        </select>
        <select
          value={entityFilter}
          onChange={(e) => setEntityFilter(e.target.value)}
          className="rounded-lg border border-border bg-muted/30 px-2 py-1 text-xs"
        >
          <option value="">All entities</option>
          {entities.map((e) => (
            <option key={e} value={e}>{e.replace("_", " ")}</option>
          ))}
        </select>
      </div>

      {/* Log List */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : logs.length === 0 ? (
        <div className="flex flex-col items-center py-12 text-center">
          <History className="h-8 w-8 text-muted-foreground/30 mb-2" />
          <p className="text-sm text-muted-foreground">No audit logs yet</p>
        </div>
      ) : (
        <div className="space-y-1">
          {logs.map((log) => {
            const config = actionConfig[log.action] || { label: log.action, icon: History, color: "text-muted-foreground" };
            const Icon = config.icon;
            return (
              <div
                key={log.id}
                className="flex items-start gap-3 rounded-lg px-3 py-2.5 hover:bg-muted/20 transition-colors"
              >
                <div className={cn("mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-muted/30", config.color)}>
                  <Icon className="h-3.5 w-3.5" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm">
                    <span className="font-medium">{log.user_name || "System"}</span>
                    <span className="text-muted-foreground"> {config.label.toLowerCase()} </span>
                    <span className="font-medium">{log.entity_type.replace("_", " ")}</span>
                    {log.entity_name && (
                      <span className="text-muted-foreground"> &quot;{log.entity_name}&quot;</span>
                    )}
                  </p>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    {timeAgo(log.created_at)}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
