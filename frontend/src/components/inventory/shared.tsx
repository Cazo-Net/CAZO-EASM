"use client";

import * as React from "react";
import {
  Globe,
  Server,
  Network,
  Plug,
  Lock,
  Cpu,
  PlusCircle,
  MinusCircle,
  RefreshCcw,
  AlertTriangle,
  Clock,
  Undo2,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { AssetType, InventoryAsset, InventoryChange } from "@/lib/api-inventory";

export const TYPE_META: Record<AssetType, { label: string; plural: string; icon: LucideIcon }> = {
  domain: { label: "Domain", plural: "Domains", icon: Globe },
  host: { label: "Host", plural: "Hosts", icon: Server },
  ip: { label: "IP address", plural: "IP addresses", icon: Network },
  service: { label: "Service", plural: "Services", icon: Plug },
  certificate: { label: "Certificate", plural: "Certificates", icon: Lock },
  technology: { label: "Technology", plural: "Technologies", icon: Cpu },
};

export const TYPE_ORDER: AssetType[] = ["host", "service", "certificate", "technology", "ip", "domain"];

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function relativeTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  const sec = Math.round((Date.now() - d.getTime()) / 1000);
  if (sec < 60) return "just now";
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  if (day < 30) return `${day}d ago`;
  return formatDate(value);
}

export function daysUntil(value: string | null | undefined): number | null {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  return Math.floor((d.getTime() - Date.now()) / 86_400_000);
}

/** One-line description of an asset for the table's Details column. */
export function assetDetails(a: InventoryAsset): string {
  const at = a.attributes || {};
  switch (a.type) {
    case "host": {
      const ips: string[] = at.ip_addresses || [];
      const parts = [];
      if (ips.length) parts.push(ips.slice(0, 2).join(", ") + (ips.length > 2 ? ` +${ips.length - 2}` : ""));
      if (a.services) parts.push(`${a.services} open port${a.services === 1 ? "" : "s"}`);
      if (a.technologies) parts.push(`${a.technologies} tech`);
      return parts.join(" · ") || "No open ports seen";
    }
    case "service":
      return [at.service, at.product, at.version].filter(Boolean).join(" ") || "Unidentified service";
    case "certificate": {
      const d = daysUntil(at.not_after);
      const exp = d === null ? "" : d < 0 ? `expired ${-d}d ago` : `expires in ${d}d`;
      return [at.issuer, exp].filter(Boolean).join(" · ");
    }
    case "technology":
      return [at.version && `v${at.version}`, at.category].filter(Boolean).join(" · ") || "Version not detected";
    case "ip":
      return a.parent ? `Resolved from ${a.parent}` : "";
    default:
      return "Monitored root domain";
  }
}

export function assetTitle(a: InventoryAsset): string {
  if (a.type === "certificate") return a.label || a.value;
  if (a.type === "technology") return `${a.label}${a.parent ? ` on ${a.parent}` : ""}`;
  if (a.type === "service") return a.label;
  return a.value;
}

export function StateBadge({ asset }: { asset: InventoryAsset }) {
  const missing = asset.state === "missing";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium",
        missing
          ? "border-border bg-muted text-muted-foreground"
          : "border-success/30 bg-success/10 text-success"
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", missing ? "bg-muted-foreground" : "bg-success")} />
      {missing ? "Missing" : "Active"}
    </span>
  );
}

const SEV_CLASS: Record<string, string> = {
  critical: "border-severity-critical/30 bg-severity-critical/10 text-severity-critical",
  high: "border-severity-high/30 bg-severity-high/10 text-severity-high",
  medium: "border-severity-medium/30 bg-severity-medium/10 text-severity-medium",
  low: "border-severity-low/30 bg-severity-low/10 text-severity-low",
};

export function SeverityTag({ severity }: { severity: string }) {
  const cls = SEV_CLASS[severity];
  if (!cls) return null;
  return (
    <span className={cn("rounded-full border px-2 py-0.5 text-[11px] font-medium capitalize", cls)}>
      {severity}
    </span>
  );
}

const EVENT_META: Record<string, { icon: LucideIcon; tone: string; label: string }> = {
  asset_new: { icon: PlusCircle, tone: "text-info", label: "New asset" },
  service_new: { icon: PlusCircle, tone: "text-warning", label: "New open port" },
  service_closed: { icon: MinusCircle, tone: "text-muted-foreground", label: "Port closed" },
  service_changed: { icon: RefreshCcw, tone: "text-muted-foreground", label: "Service changed" },
  cert_new: { icon: Lock, tone: "text-info", label: "New certificate" },
  cert_changed: { icon: RefreshCcw, tone: "text-info", label: "Certificate replaced" },
  cert_expiring: { icon: Clock, tone: "text-warning", label: "Certificate expiring" },
  tech_new: { icon: PlusCircle, tone: "text-muted-foreground", label: "New technology" },
  tech_changed: { icon: RefreshCcw, tone: "text-muted-foreground", label: "Version changed" },
  tech_removed: { icon: MinusCircle, tone: "text-muted-foreground", label: "Technology removed" },
  ip_changed: { icon: RefreshCcw, tone: "text-muted-foreground", label: "IP changed" },
  asset_missing: { icon: MinusCircle, tone: "text-destructive", label: "Disappeared" },
  asset_reappeared: { icon: Undo2, tone: "text-success", label: "Came back" },
  finding_new: { icon: AlertTriangle, tone: "text-destructive", label: "New finding" },
};

export function eventMeta(event: string) {
  return EVENT_META[event] || { icon: RefreshCcw, tone: "text-muted-foreground", label: event.replace(/_/g, " ") };
}

export function ChangeRow({
  change,
  onOpenAsset,
  compact,
}: {
  change: InventoryChange;
  onOpenAsset?: (id: string) => void;
  compact?: boolean;
}) {
  const meta = eventMeta(change.event);
  const Icon = meta.icon;
  const clickable = Boolean(onOpenAsset && change.asset_id);
  const body = (
    <>
      <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", meta.tone)} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className={cn("break-words text-sm", compact ? "" : "font-medium")}>{change.summary}</p>
        <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
          <span>{meta.label}</span>
          {!compact && change.root_domain && <span className="font-mono">{change.root_domain}</span>}
          <SeverityTag severity={change.severity} />
        </p>
      </div>
      <time
        className="shrink-0 whitespace-nowrap text-xs tabular-nums text-muted-foreground"
        dateTime={change.detected_at || undefined}
        title={change.detected_at ? new Date(change.detected_at).toLocaleString() : undefined}
      >
        {relativeTime(change.detected_at)}
      </time>
    </>
  );
  const cls = "flex w-full items-start gap-3 px-4 py-3 text-left";
  return clickable ? (
    <button
      type="button"
      onClick={() => onOpenAsset!(change.asset_id!)}
      className={cn(cls, "transition-colors hover:bg-muted/40 focus-visible:bg-muted/40 focus-visible:outline-none")}
    >
      {body}
    </button>
  ) : (
    <div className={cls}>{body}</div>
  );
}

export function Toggle({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50",
        checked ? "border-primary bg-primary" : "border-border bg-muted"
      )}
    >
      <span
        className={cn(
          "inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform",
          checked ? "translate-x-[18px]" : "translate-x-[3px]"
        )}
      />
    </button>
  );
}
