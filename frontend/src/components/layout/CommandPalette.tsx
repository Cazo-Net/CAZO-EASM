"use client";

import * as React from "react";
import { Command } from "cmdk";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import {
  LayoutDashboard,
  ScanSearch,
  Globe,
  Bug,
  Network,
  Search,
  Waypoints,
  ShieldCheck,
  Radar,
  Settings,
  FileText,
  Sun,
  Moon,
  LogOut,
  Shield,
  Wallet,
  Eye,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";

interface CommandItem {
  id: string;
  label: string;
  hint?: string;
  icon: React.ComponentType<{ className?: string }>;
  group: string;
  action: () => void;
  keywords?: string[];
}

export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const { logout } = useAuth();
  const [query, setQuery] = React.useState("");

  const run = React.useCallback(
    (fn: () => void) => {
      onOpenChange(false);
      setQuery("");
      fn();
    },
    [onOpenChange]
  );

  const items: CommandItem[] = [
    {
      id: "nav-dashboard",
      label: "Go to Dashboard",
      group: "Navigation",
      icon: LayoutDashboard,
      action: () => router.push("/dashboard"),
    },
    {
      id: "nav-scans",
      label: "Go to Scans",
      group: "Navigation",
      icon: ScanSearch,
      action: () => router.push("/scans"),
    },
    {
      id: "nav-blockchain",
      label: "Go to Blockchain Intelligence",
      group: "Navigation",
      icon: Wallet,
      keywords: ["wallet", "ethereum", "on-chain"],
      action: () => router.push("/blockchain"),
    },
    {
      id: "nav-darkweb",
      label: "Go to Dark Web & Threat Intelligence",
      group: "Navigation",
      icon: Eye,
      keywords: ["dark", "onion", "tor", "credential"],
      action: () => router.push("/darkweb"),
    },
    {
      id: "nav-newscan",
      label: "Start New Scan",
      group: "Navigation",
      icon: ScanSearch,
      keywords: ["create", "launch"],
      action: () => router.push("/scan/new"),
    },
    {
      id: "nav-assets",
      label: "Go to Assets",
      group: "Navigation",
      icon: Globe,
      action: () => router.push("/assets"),
    },
    {
      id: "nav-vulns",
      label: "Go to Vulnerabilities",
      group: "Navigation",
      icon: Bug,
      keywords: ["cve", "security"],
      action: () => router.push("/vulnerabilities"),
    },
    {
      id: "nav-dns",
      label: "Go to DNS Records",
      group: "Navigation",
      icon: Network,
      action: () => router.push("/dns"),
    },
    {
      id: "nav-whois",
      label: "Go to WHOIS",
      group: "Navigation",
      icon: Search,
      action: () => router.push("/whois"),
    },
    {
      id: "nav-graph",
      label: "Go to Attack Graph",
      group: "Navigation",
      icon: Waypoints,
      keywords: ["map", "relations"],
      action: () => router.push("/graph"),
    },
    {
      id: "nav-scopes",
      label: "Go to Authorized Scopes",
      group: "Navigation",
      icon: ShieldCheck,
      keywords: ["authorization", "perimeter", "allowlist"],
      action: () => router.push("/scopes"),
    },
    {
      id: "nav-reports",
      label: "Go to Reports",
      group: "Navigation",
      icon: FileText,
      action: () => router.push("/reports"),
    },
    {
      id: "nav-settings",
      label: "Go to Settings",
      group: "System",
      icon: Settings,
      action: () => router.push("/settings"),
    },
    {
      id: "toggle-theme",
      label: "Toggle Theme",
      group: "System",
      icon: theme === "dark" ? Sun : Moon,
      keywords: ["dark", "light", "mode"],
      action: () => setTheme(theme === "dark" ? "light" : "dark"),
    },
    {
      id: "logout",
      label: "Sign Out",
      group: "System",
      icon: LogOut,
      keywords: ["exit", "logoff"],
      action: logout,
    },
  ];

  const groups = React.useMemo(() => {
    const map = new Map<string, CommandItem[]>();
    for (const item of items) {
      if (!map.has(item.group)) map.set(item.group, []);
      map.get(item.group)!.push(item);
    }
    return Array.from(map.entries());
  }, [items]);

  return (
    <Command.Dialog
      open={open}
      onOpenChange={onOpenChange}
      label="Command Palette"
      className="fixed left-1/2 top-[18%] z-[100] w-[92vw] max-w-xl -translate-x-1/2 overflow-hidden rounded-xl border border-border bg-card shadow-elevation-3"
    >
      <div className="flex items-center gap-3 border-b border-border px-4">
        <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
        <Command.Input
          value={query}
          onValueChange={setQuery}
          placeholder="Search commands, pages, actions…"
          className="h-12 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        />
        <kbd className="hidden rounded border border-border bg-surface-2 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground sm:block">
          ESC
        </kbd>
      </div>
      <Command.List className="max-h-[50vh] overflow-y-auto p-2">
        <Command.Empty className="px-3 py-8 text-center text-sm text-muted-foreground">
          No results found.
        </Command.Empty>
        {groups.map(([group, list]) => (
          <Command.Group
            key={group}
            heading={group}
            className="px-1 pb-2 pt-1 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wide [&_[cmdk-group-heading]]:text-muted-foreground"
          >
            {list.map((item) => (
              <Command.Item
                key={item.id}
                value={`${item.label} ${item.keywords?.join(" ") ?? ""}`}
                onSelect={() => run(item.action)}
                className={cn(
                  "flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
                  "data-[selected=true]:bg-brand/10 data-[selected=true]:text-brand"
                )}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                <span className="flex-1">{item.label}</span>
              </Command.Item>
            ))}
          </Command.Group>
        ))}
      </Command.List>
      <div className="flex items-center justify-between border-t border-border px-4 py-2 text-[11px] text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <Shield className="h-3 w-3 text-brand" /> CAZO EASM Command
        </span>
        <span className="flex items-center gap-2">
          <kbd className="rounded border border-border bg-surface-2 px-1.5 py-0.5">↑</kbd>
          <kbd className="rounded border border-border bg-surface-2 px-1.5 py-0.5">↓</kbd>
          <span>navigate</span>
          <kbd className="rounded border border-border bg-surface-2 px-1.5 py-0.5">↵</kbd>
          <span>select</span>
        </span>
      </div>
    </Command.Dialog>
  );
}
