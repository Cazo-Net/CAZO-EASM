"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useMemo } from "react";
import {
  Shield,
  LayoutDashboard,
  ScanSearch,
  Globe,
  FileText,
  Settings,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  LogOut,
  Bug,
  Network,
  Search,
  Waypoints,
  ShieldCheck,
  Radar,
  Ghost,
  Zap,
  ChevronsUpDown,
  Building,
  CreditCard,
  History,
  BarChart3,
  MessagesSquare,
  Boxes,
  BookOpen,
  Wallet,
  Eye,
  Link2,
  Webhook,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Separator } from "@/components/ui/separator";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useAuth } from "@/contexts/AuthContext";
import { CazoMark } from "@/components/marketing/CazoLogo";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";

const navSections = [
  {
    label: "Overview",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/change-feed", label: "Change feed", icon: History },
    ],
  },
  {
    label: "Attack surface",
    items: [
      { href: "/assets", label: "Assets", icon: Globe },
      { href: "/shadow-assets", label: "Shadow assets", icon: Ghost },
      { href: "/assets/360", label: "Asset 360°", icon: Boxes },
      { href: "/graph", label: "Attack graph", icon: Waypoints },
      { href: "/dns", label: "DNS records", icon: Network },
      { href: "/whois", label: "WHOIS", icon: Search },
    ],
  },
  {
    label: "Risk",
    items: [
      { href: "/vulnerabilities", label: "Findings", icon: Bug },
      { href: "/supply-chain", label: "Supply chain", icon: Boxes },
    ],
  },
  {
    label: "Operations",
    items: [
      { href: "/scans", label: "Scans", icon: ScanSearch },
      { href: "/scopes", label: "Authorized scopes", icon: ShieldCheck },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { href: "/intel", label: "Threat intel", icon: Zap },
      { href: "/darkweb", label: "Dark web", icon: Eye },
      { href: "/blockchain", label: "Blockchain", icon: Wallet },
    ],
  },
  {
    label: "Reporting",
    items: [
      { href: "/reports", label: "Reports", icon: FileText },
      { href: "/reports/executive", label: "Executive report", icon: BarChart3 },
      { href: "/compare", label: "Compare scans", icon: Waypoints },
      { href: "/canvas", label: "Investigation canvas", icon: Network },
    ],
  },
  {
    label: "Team",
    items: [
      { href: "/collab-demo", label: "Comments", icon: MessagesSquare },
      { href: "/docs", label: "Docs", icon: BookOpen },
    ],
  },
];

const ALL_HREFS = navSections.flatMap((s) => s.items.map((i) => i.href)).concat("/settings");

interface SidebarProps {
  collapsed: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
}

export function Sidebar({ collapsed, onCollapsedChange }: SidebarProps) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [orgMenuOpen, setOrgMenuOpen] = useState(false);

  // Sections are open by default; people can fold the ones they don't use.
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>({});

  // Only the most specific matching route is active, so /assets/360 does
  // not also light up /assets.
  const activeHref = useMemo(() => {
    let best = "";
    for (const href of ALL_HREFS) {
      if ((pathname === href || pathname.startsWith(href + "/")) && href.length > best.length) {
        best = href;
      }
    }
    return best;
  }, [pathname]);

  function isSectionExpanded(label: string): boolean {
    return !collapsedSections[label];
  }

  function toggleSection(label: string) {
    setCollapsedSections((prev) => ({
      ...prev,
      [label]: !prev[label],
    }));
  }

  function isActive(href: string) {
    return href === activeHref;
  }

  function getInitials() {
    if (user?.full_name) {
      return user.full_name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2);
    }
    if (user?.email) {
      return user.email.slice(0, 2).toUpperCase();
    }
    return "AS";
  }

  const sidebarWidth = collapsed ? "w-[64px]" : "w-[248px]";

  const itemClass = (active: boolean) =>
    cn(
      "group relative flex items-center gap-2.5 rounded-md px-2.5 py-[7px] text-[13px] font-medium transition-colors duration-150",
      active
        ? "bg-primary/10 text-foreground"
        : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
      collapsed && "justify-center px-0"
    );
  const iconClass = (active: boolean) =>
    cn(
      "h-4 w-4 shrink-0 transition-colors",
      active ? "text-primary" : "text-muted-foreground/80 group-hover:text-foreground"
    );

  return (
    <TooltipProvider delayDuration={0}>
      <aside
        className={cn(
          "relative flex h-screen flex-col border-r border-border bg-card transition-[width] duration-200 ease-out shrink-0",
          sidebarWidth
        )}
        role="navigation"
        aria-label="Main navigation"
      >
        {/* Workspace / Brand Header */}
        <div className={cn("flex h-14 items-center gap-2.5 border-b border-border shrink-0", collapsed ? "justify-center px-0" : "px-4")}>
          <Link href="/dashboard" className="flex items-center gap-2.5 min-w-0">
            <CazoMark className="h-7 w-7 shrink-0" />
            {!collapsed && (
              <span className="truncate text-[15px] font-semibold tracking-tight text-foreground">
                CAZO <span className="font-medium text-muted-foreground">EASM</span>
              </span>
            )}
          </Link>
        </div>

        {/* Primary action */}
        <div className={cn("pt-3 pb-1 shrink-0", collapsed ? "flex justify-center" : "px-3")}>
          {collapsed ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <Link href="/scan/new">
                  <Button size="icon" className="h-9 w-9" aria-label="New scan">
                    <Radar className="h-4 w-4" />
                  </Button>
                </Link>
              </TooltipTrigger>
              <TooltipContent side="right" sideOffset={8}>
                New scan
              </TooltipContent>
            </Tooltip>
          ) : (
            <Link href="/scan/new" className="block">
              <Button size="sm" className="h-9 w-full justify-start gap-2">
                <Radar className="h-4 w-4" />
                New scan
              </Button>
            </Link>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-3 py-2 sidebar-scroll" aria-label="Main menu">
          {navSections.map((section) => {
            const expanded = collapsed || isSectionExpanded(section.label);
            return (
              <div key={section.label} className={cn(collapsed ? "mb-2 border-b border-border/60 pb-2 last:border-0" : "mb-3")}>
                {!collapsed && (
                  <button
                    onClick={() => toggleSection(section.label)}
                    className="group/section mb-1 flex w-full items-center justify-between rounded px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.06em] text-muted-foreground/70 transition-colors hover:text-foreground"
                    aria-expanded={expanded}
                  >
                    <span>{section.label}</span>
                    <ChevronDown
                      className={cn(
                        "h-3 w-3 opacity-0 transition-all duration-150 group-hover/section:opacity-100",
                        expanded ? "rotate-0" : "-rotate-90 opacity-100"
                      )}
                    />
                  </button>
                )}
                <div className="space-y-px">
                  {section.items
                    .filter((item) => expanded || isActive(item.href))
                    .map((item) => {
                      const active = isActive(item.href);
                      const link = (
                        <Link
                          key={item.href}
                          href={item.href}
                          className={itemClass(active)}
                          aria-current={active ? "page" : undefined}
                          aria-label={collapsed ? item.label : undefined}
                        >
                          {active && (
                            <span className="absolute -left-3 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-r bg-primary" aria-hidden="true" />
                          )}
                          <item.icon className={iconClass(active)} />
                          {!collapsed && <span className="truncate">{item.label}</span>}
                        </Link>
                      );
                      if (!collapsed) return <div key={item.href}>{link}</div>;
                      return (
                        <Tooltip key={item.href}>
                          <TooltipTrigger asChild>{link}</TooltipTrigger>
                          <TooltipContent side="right" sideOffset={8}>
                            {item.label}
                          </TooltipContent>
                        </Tooltip>
                      );
                    })}
                </div>
              </div>
            );
          })}
        </nav>

        {/* Bottom Section */}
        <div className="border-t border-border px-3 py-3 shrink-0">
          {/* Settings */}
          {(() => {
            const active = isActive("/settings");
            const link = (
              <Link
                href="/settings"
                className={itemClass(active)}
                aria-current={active ? "page" : undefined}
              >
                {active && (
                  <span className="absolute -left-3 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-r bg-primary" aria-hidden="true" />
                )}
                <Settings className={iconClass(active)} />
                {!collapsed && <span>Settings</span>}
              </Link>
            );

            if (collapsed) {
              return (
                <Tooltip>
                  <TooltipTrigger asChild>{link}</TooltipTrigger>
                  <TooltipContent side="right" sideOffset={8}>
                    Settings
                  </TooltipContent>
                </Tooltip>
              );
            }
            return link;
          })()}

          <Separator className="my-2.5 bg-border/50" />

          {/* Organization Switcher (expanded only) */}
          {!collapsed && user?.organization_id && (
            <DropdownMenu open={orgMenuOpen} onOpenChange={setOrgMenuOpen}>
              <DropdownMenuTrigger asChild>
                <button
                  className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors hover:bg-muted/40 mb-1"
                  aria-label="Organization menu"
                >
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-cyan-signal/10">
                    <Building className="h-3.5 w-3.5 text-cyan-signal" />
                  </div>
                  <div className="flex-1 min-w-0 text-left">
                    <p className="text-xs font-medium truncate">Organization</p>
                    <p className="text-[10px] text-muted-foreground/60 truncate font-mono">
                      {user.organization_id.slice(0, 12)}...
                    </p>
                  </div>
                  <ChevronsUpDown className="h-3.5 w-3.5 text-muted-foreground/50 shrink-0" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-56" side="top">
                <Link href="/settings/organization" passHref legacyBehavior>
                  <DropdownMenuItem className="text-xs" onSelect={() => setOrgMenuOpen(false)}>
                    <Building className="h-3.5 w-3.5 mr-2" />
                    Manage Organization
                  </DropdownMenuItem>
                </Link>
                <Link href="/billing" passHref legacyBehavior>
                  <DropdownMenuItem className="text-xs" onSelect={() => setOrgMenuOpen(false)}>
                    <CreditCard className="h-3.5 w-3.5 mr-2" />
                    Billing &amp; plan
                  </DropdownMenuItem>
                </Link>
              </DropdownMenuContent>
            </DropdownMenu>
          )}

          {/* User Profile */}
          {collapsed ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="flex justify-center">
                  <Avatar className="h-8 w-8 ring-1 ring-border cursor-pointer">
                    <AvatarFallback className="bg-primary/15 text-xs font-semibold text-primary">
                      {getInitials()}
                    </AvatarFallback>
                  </Avatar>
                </div>
              </TooltipTrigger>
              <TooltipContent side="right" sideOffset={8}>
                <p className="font-medium">{user?.full_name || user?.email || "User"}</p>
                {user?.email && (
                  <p className="text-xs text-muted-foreground">{user.email}</p>
                )}
              </TooltipContent>
            </Tooltip>
          ) : (
            <div className="flex items-center gap-2.5 px-2 py-1.5">
              <Avatar className="h-8 w-8 ring-1 ring-border shrink-0">
                <AvatarFallback className="bg-primary/15 text-xs font-semibold text-primary">
                  {getInitials()}
                </AvatarFallback>
              </Avatar>
              <div className="flex-1 overflow-hidden min-w-0">
                <p className="truncate text-xs font-medium">
                  {user?.full_name || user?.email || "User"}
                </p>
                <p className="truncate text-[10px] text-muted-foreground/60">
                  {user?.email || ""}
                </p>
              </div>
            </div>
          )}

          {/* Logout */}
          {collapsed ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={logout}
                  className="mt-2 flex w-full items-center justify-center rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                  aria-label="Log out"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="right" sideOffset={8}>
                Log out
              </TooltipContent>
            </Tooltip>
          ) : (
            <button
              onClick={logout}
              className="mt-2 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
              aria-label="Log out"
            >
              <LogOut className="h-4 w-4 shrink-0" />
              <span>Log out</span>
            </button>
          )}
        </div>

        {/* Collapse Toggle */}
        <button
          onClick={() => onCollapsedChange(!collapsed)}
          className="absolute -right-3 top-[70px] hidden md:flex h-6 w-6 items-center justify-center rounded-full border border-border bg-card text-muted-foreground shadow-elevation-1 transition-colors hover:text-foreground z-50"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <ChevronRight className="h-3 w-3" />
          ) : (
            <ChevronLeft className="h-3 w-3" />
          )}
        </button>
      </aside>
    </TooltipProvider>
  );
}
