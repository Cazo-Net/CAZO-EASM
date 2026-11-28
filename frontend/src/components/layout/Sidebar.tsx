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
    label: "OVERVIEW",
    items: [{ href: "/dashboard", label: "Dashboard", icon: LayoutDashboard }],
  },
  {
    label: "DISCOVERY",
    items: [
      { href: "/scans", label: "Scans", icon: ScanSearch },
      { href: "/intel", label: "Intelligence", icon: Zap },
      { href: "/blockchain", label: "Blockchain Intel", icon: Wallet },
      { href: "/darkweb", label: "Dark Web Intel", icon: Eye },
      { href: "/supply-chain", label: "Supply Chain", icon: Boxes },
      { href: "/assets", label: "Assets", icon: Globe },
      { href: "/shadow-assets", label: "Shadow Assets", icon: Ghost },
      { href: "/vulnerabilities", label: "Vulnerabilities", icon: Bug },
      { href: "/dns", label: "DNS Records", icon: Network },
      { href: "/whois", label: "WHOIS", icon: Search },
      { href: "/graph", label: "Attack Graph", icon: Waypoints },
      { href: "/scopes", label: "Authorized Scopes", icon: ShieldCheck },
      { href: "/change-feed", label: "Change Feed", icon: History },
      { href: "/assets/360", label: "Asset 360°", icon: Boxes },
    ],
  },
  {
    label: "OUTPUT",
    items: [
      { href: "/reports", label: "Reports", icon: FileText },
      { href: "/reports/executive", label: "Executive Report", icon: BarChart3 },
      { href: "/compare", label: "Compare Scans", icon: Waypoints },
      { href: "/canvas", label: "Intelligence Canvas", icon: Network },
    ],
  },
  {
    label: "COLLABORATION",
    items: [
      { href: "/collab-demo", label: "Team Comments", icon: MessagesSquare },
    ],
  },
  {
    label: "RESOURCES",
    items: [
      { href: "/docs", label: "Docs", icon: BookOpen },
    ],
  },
];

interface SidebarProps {
  collapsed: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
}

export function Sidebar({ collapsed, onCollapsedChange }: SidebarProps) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [orgMenuOpen, setOrgMenuOpen] = useState(false);

  // Track which sections are collapsed (keyed by label)
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>({});

  // Auto-expand sections that contain the active page
  const activeSectionLabels = useMemo(() => {
    const active = new Set<string>();
    for (const section of navSections) {
      for (const item of section.items) {
        if (isActive(item.href)) {
          active.add(section.label);
        }
      }
    }
    return active;
  }, [pathname]);

  function isSectionExpanded(label: string): boolean {
    if (label in collapsedSections) {
      return !collapsedSections[label];
    }
    // Default: OVERVIEW always expanded, others expanded unless collapsed
    return activeSectionLabels.has(label);
  }

  function toggleSection(label: string) {
    setCollapsedSections((prev) => ({
      ...prev,
      [label]: !prev[label],
    }));
  }

  function isActive(href: string) {
    return href === "/" ? pathname === "/" : pathname.startsWith(href);
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

  const sidebarWidth = collapsed ? "w-[68px]" : "w-64";

  return (
    <TooltipProvider delayDuration={0}>
      <aside
        className={cn(
          "flex h-screen flex-col border-r border-border/50 transition-all duration-300 ease-in-out shrink-0",
          "bg-card/90 backdrop-blur-xl",
          sidebarWidth
        )}
        role="navigation"
        aria-label="Main navigation"
      >
        {/* Workspace / Brand Header */}
        <div className="flex h-14 items-center gap-3 border-b border-border/50 px-4 shrink-0">
          <Link href="/dashboard" className="flex items-center gap-3 min-w-0">
            <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-void border border-border/50 overflow-hidden shadow-glow-sm">
              <CazoMark className="h-6 w-6" />
              <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-phosphor/20 to-cyan-signal/10 blur-md" />
            </div>
            {!collapsed && (
              <div className="flex flex-col min-w-0">
                <span className="text-sm font-bold tracking-tight gradient-text truncate font-display">
                  CAZO EASM
                </span>
                <span className="text-[10px] text-muted-foreground/60 truncate font-mono">
                  Enterprise
                </span>
              </div>
            )}
          </Link>
        </div>

        {/* Quick Actions - only visible when expanded */}
        {!collapsed && (
          <div className="px-3 pt-3 pb-1 shrink-0">
            <Link href="/scan/new">
              <Button
                size="sm"
                className="w-full justify-start gap-2 h-9 gradient-brand text-void shadow-glow-sm text-xs font-semibold font-mono"
              >
                <Zap className="h-3.5 w-3.5" />
                Quick Scan
              </Button>
            </Link>
          </div>
        )}

        {collapsed && (
          <div className="flex justify-center pt-3 pb-1 shrink-0">
            <Tooltip>
              <TooltipTrigger asChild>
                <Link href="/scan/new">
                  <Button
                    size="icon"
                    className="h-9 w-9 gradient-brand text-void shadow-glow-sm"
                    aria-label="Quick Scan"
                  >
                    <Zap className="h-4 w-4" />
                  </Button>
                </Link>
              </TooltipTrigger>
              <TooltipContent side="right" sideOffset={8}>
                Quick Scan
              </TooltipContent>
            </Tooltip>
          </div>
        )}

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-3 py-3 sidebar-scroll" aria-label="Main menu">
          {navSections.map((section) => {
            const expanded = collapsed ? false : isSectionExpanded(section.label);
            return (
              <div key={section.label} className="mb-4">
                {!collapsed && (
                  <button
                    onClick={() => toggleSection(section.label)}
                    className="mb-1.5 flex w-full items-center justify-between px-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground/40 font-mono hover:text-muted-foreground/70 transition-colors"
                    aria-expanded={expanded}
                  >
                    <span>{section.label}</span>
                    <ChevronDown
                      className={cn(
                        "h-3 w-3 transition-transform duration-200",
                        expanded ? "rotate-0" : "-rotate-90"
                      )}
                    />
                  </button>
                )}
                {expanded && (
                  <div className="space-y-0.5">
                    {section.items.map((item) => {
                      const active = isActive(item.href);
                      const link = (
                        <Link
                          key={item.href}
                          href={item.href}
                          className={cn(
                            "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200",
                            active
                              ? "bg-phosphor/8 text-phosphor shadow-glow-sm"
                              : "text-muted-foreground hover:bg-muted/40 hover:text-foreground"
                          )}
                          aria-current={active ? "page" : undefined}
                        >
                          {active && (
                            <div className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-gradient-to-b from-phosphor to-cyan-signal" />
                          )}
                          <item.icon
                            className={cn(
                              "h-4 w-4 shrink-0 transition-colors duration-200",
                              active
                                ? "text-phosphor"
                                : "text-muted-foreground group-hover:text-foreground"
                            )}
                          />
                          <span className="truncate">{item.label}</span>
                        </Link>
                      );
                      return <div key={item.href}>{link}</div>;
                    })}
                  </div>
                )}
                {!collapsed && !expanded && (
                  <div className="space-y-0.5">
                    {section.items
                      .filter((item) => isActive(item.href))
                      .map((item) => {
                        const link = (
                          <Link
                            key={item.href}
                            href={item.href}
                            className="group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium bg-phosphor/8 text-phosphor shadow-glow-sm"
                            aria-current="page"
                          >
                            <div className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-gradient-to-b from-phosphor to-cyan-signal" />
                            <item.icon className="h-4 w-4 shrink-0 text-phosphor" />
                            <span className="truncate">{item.label}</span>
                          </Link>
                        );
                        return <div key={item.href}>{link}</div>;
                      })}
                  </div>
                )}
                {collapsed && (
                  <div className="space-y-0.5">
                    {section.items.map((item) => {
                      const active = isActive(item.href);
                      const link = (
                        <Link
                          key={item.href}
                          href={item.href}
                          className={cn(
                            "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200",
                            active
                              ? "bg-phosphor/8 text-phosphor shadow-glow-sm"
                              : "text-muted-foreground hover:bg-muted/40 hover:text-foreground"
                          )}
                          aria-current={active ? "page" : undefined}
                        >
                          {active && (
                            <div className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-gradient-to-b from-phosphor to-cyan-signal" />
                          )}
                          <item.icon
                            className={cn(
                              "h-4 w-4 shrink-0 transition-colors duration-200",
                              active
                                ? "text-phosphor"
                                : "text-muted-foreground group-hover:text-foreground"
                            )}
                          />
                        </Link>
                      );
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
                )}
              </div>
            );
          })}
        </nav>

        {/* Bottom Section */}
        <div className="border-t border-border/50 px-3 py-3 shrink-0">
          {/* Settings */}
          {(() => {
            const active = isActive("/settings");
            const link = (
              <Link
                href="/settings"
                className={cn(
                  "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200",
                  active
                    ? "bg-phosphor/8 text-phosphor shadow-glow-sm"
                    : "text-muted-foreground hover:bg-muted/40 hover:text-foreground"
                )}
                aria-current={active ? "page" : undefined}
              >
                {active && (
                  <div className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-gradient-to-b from-phosphor to-cyan-signal" />
                )}
                <Settings
                  className={cn(
                    "h-4 w-4 shrink-0 transition-colors duration-200",
                    active
                      ? "text-phosphor"
                      : "text-muted-foreground group-hover:text-foreground"
                  )}
                />
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
                  <Avatar className="h-8 w-8 ring-2 ring-border ring-offset-2 ring-offset-card cursor-pointer">
                    <AvatarFallback className="bg-phosphor/10 text-xs font-semibold text-phosphor font-mono">
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
              <Avatar className="h-8 w-8 ring-2 ring-border ring-offset-2 ring-offset-card shrink-0">
                <AvatarFallback className="bg-phosphor/10 text-xs font-semibold text-phosphor font-mono">
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
          className="absolute -right-3 top-20 flex h-6 w-6 items-center justify-center rounded-full border border-border bg-card text-muted-foreground shadow-lg transition-colors hover:text-foreground z-50"
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
