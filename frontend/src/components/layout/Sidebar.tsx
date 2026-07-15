"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Shield,
  LayoutDashboard,
  ScanSearch,
  Globe,
  FileText,
  Settings,
  ChevronLeft,
  ChevronRight,
  LogOut,
  Bug,
  Network,
  Search,
  Waypoints,
  Sparkles,
  Bot,
  LayoutList,
  BookOpen,
  Lightbulb,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Separator } from "@/components/ui/separator";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useAuth } from "@/contexts/AuthContext";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const navSections = [
  {
    label: "OVERVIEW",
    items: [{ href: "/dashboard", label: "Dashboard", icon: LayoutDashboard }],
  },
  {
    label: "DISCOVERY",
    items: [
      { href: "/scans", label: "Scans", icon: ScanSearch },
      { href: "/assets", label: "Assets", icon: Globe },
      { href: "/vulnerabilities", label: "Vulnerabilities", icon: Bug },
      { href: "/dns", label: "DNS Records", icon: Network },
      { href: "/whois", label: "WHOIS", icon: Search },
      { href: "/graph", label: "Attack Graph", icon: Waypoints },
    ],
  },
  {
    label: "AI INTELLIGENCE",
    items: [
      { href: "/ai", label: "AI Dashboard", icon: Sparkles },
      { href: "/ai/copilot", label: "AI Copilot", icon: Bot },
      { href: "/ai/knowledge", label: "Knowledge Center", icon: BookOpen },
      { href: "/ai/recommendations", label: "Recommendations", icon: Lightbulb },
      { href: "/ai/settings", label: "AI Settings", icon: Settings },
    ],
  },
  {
    label: "OUTPUT",
    items: [
      { href: "/reports", label: "Reports", icon: FileText },
      { href: "/compare", label: "Compare Scans", icon: Waypoints },
      { href: "/canvas", label: "Intelligence Canvas", icon: Network },
    ],
  },
];

const bottomItems = [{ href: "/settings", label: "Settings", icon: Settings }];

interface SidebarProps {
  collapsed: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
}

export function Sidebar({ collapsed, onCollapsedChange }: SidebarProps) {
  const pathname = usePathname();
  const { user, logout } = useAuth();

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

  return (
    <TooltipProvider delayDuration={0}>
      <aside
        className={cn(
          "fixed left-0 top-0 z-50 flex h-screen flex-col border-r border-border/50 transition-all duration-300 ease-in-out",
          "bg-card/80 backdrop-blur-xl",
          collapsed ? "w-[68px]" : "w-64"
        )}
      >
        <div className="flex h-16 items-center gap-3 border-b border-border/50 px-4">
          <div className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#09090B] border border-border/50 overflow-hidden">
            <img src="/icon.ico" alt="AttackSec" className="h-7 w-7 object-contain" />
            <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-primary to-cyan-400 opacity-20 blur-md" />
          </div>
          {!collapsed && (
            <span className="text-lg font-bold tracking-tight gradient-text whitespace-nowrap">
              AttackSec
            </span>
          )}
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4">
          {navSections.map((section) => (
            <div key={section.label} className="mb-5">
              {!collapsed && (
                <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60">
                  {section.label}
                </p>
              )}
              <div className="space-y-1">
                {section.items.map((item) => {
                  const active = isActive(item.href);
                  const link = (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={cn(
                        "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200",
                        active
                          ? "bg-primary/10 text-primary"
                          : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                      )}
                    >
                      {active && (
                        <div className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-gradient-to-b from-primary to-cyan-400" />
                      )}
                      <item.icon
                        className={cn(
                          "h-4 w-4 shrink-0 transition-colors duration-200",
                          active
                            ? "text-primary"
                            : "text-muted-foreground group-hover:text-foreground"
                        )}
                      />
                      {!collapsed && <span>{item.label}</span>}
                    </Link>
                  );

                  if (collapsed) {
                    return (
                      <Tooltip key={item.href}>
                        <TooltipTrigger asChild>{link}</TooltipTrigger>
                        <TooltipContent side="right" sideOffset={8}>
                          {item.label}
                        </TooltipContent>
                      </Tooltip>
                    );
                  }
                  return <div key={item.href}>{link}</div>;
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-border/50 px-3 py-3">
          {bottomItems.map((item) => {
            const active = isActive(item.href);
            const link = (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200",
                  active
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                )}
              >
                {active && (
                  <div className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-gradient-to-b from-primary to-cyan-400" />
                )}
                <item.icon
                  className={cn(
                    "h-4 w-4 shrink-0 transition-colors duration-200",
                    active
                      ? "text-primary"
                      : "text-muted-foreground group-hover:text-foreground"
                  )}
                />
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );

            if (collapsed) {
              return (
                <Tooltip key={item.href}>
                  <TooltipTrigger asChild>{link}</TooltipTrigger>
                  <TooltipContent side="right" sideOffset={8}>
                    {item.label}
                  </TooltipContent>
                </Tooltip>
              );
            }
            return <div key={item.href}>{link}</div>;
          })}

          <Separator className="my-3 bg-border/50" />

          {collapsed ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="flex justify-center">
                  <Avatar className="h-8 w-8 ring-2 ring-primary/30 ring-offset-2 ring-offset-card">
                    <AvatarFallback className="bg-gradient-to-br from-primary/20 to-cyan-400/20 text-xs font-semibold text-primary">
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
            <div className="flex items-center gap-3 px-2 py-1.5">
              <Avatar className="h-9 w-9 ring-2 ring-primary/30 ring-offset-2 ring-offset-card">
                <AvatarFallback className="bg-gradient-to-br from-primary/20 to-cyan-400/20 text-xs font-semibold text-primary">
                  {getInitials()}
                </AvatarFallback>
              </Avatar>
              <div className="flex-1 overflow-hidden">
                <p className="truncate text-sm font-medium">
                  {user?.full_name || user?.email || "User"}
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  {user?.email || ""}
                </p>
              </div>
            </div>
          )}

          {collapsed ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={logout}
                  className="mt-2 flex w-full items-center justify-center rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="right" sideOffset={8}>
                Logout
              </TooltipContent>
            </Tooltip>
          ) : (
            <button
              onClick={logout}
              className="mt-2 flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
            >
              <LogOut className="h-4 w-4 shrink-0" />
              <span>Logout</span>
            </button>
          )}
        </div>

        <button
          onClick={() => onCollapsedChange(!collapsed)}
          className="absolute -right-3 top-20 flex h-6 w-6 items-center justify-center rounded-full border border-border bg-card text-muted-foreground shadow-lg transition-colors hover:text-foreground"
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
