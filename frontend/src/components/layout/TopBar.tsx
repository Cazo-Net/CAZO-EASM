"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import {
  Search,
  ScanSearch,
  Sun,
  Moon,
  Menu,
  Command,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useAuth } from "@/contexts/AuthContext";
import { useTheme } from "next-themes";
import { NotificationCenter } from "@/components/notifications/NotificationCenter";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const routeTitles: Record<string, string> = {
  "/": "CAZO EASM",
  "/dashboard": "Dashboard",
  "/scans": "Scans",
  "/scanner-v2": "Scanner v2",
  "/assets": "Assets",
  "/reports": "Reports",
  "/settings": "Settings",
  "/vulnerabilities": "Vulnerabilities",
  "/dns": "DNS Records",
  "/whois": "WHOIS Records",
  "/graph": "Attack Graph",
  "/scan/new": "New Scan",
  "/compare": "Compare Scans",
  "/canvas": "Intelligence Canvas",
  "/blockchain": "Blockchain Intelligence",
  "/darkweb": "Dark Web Intelligence",
};

interface TopBarProps {
  sidebarCollapsed: boolean;
  onToggleSidebar?: () => void;
  onOpenPalette?: () => void;
}

export function TopBar({ sidebarCollapsed, onToggleSidebar, onOpenPalette }: TopBarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();

  const pageTitle =
    routeTitles[pathname] ||
    pathname
      .split("/")
      .filter(Boolean)
      .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
      .join(" / ");

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
      <header
        className={cn(
          "flex h-14 shrink-0 items-center border-b border-border/50 bg-background/80 backdrop-blur-xl z-40 transition-all duration-300"
        )}
        role="banner"
      >
        <div className="flex flex-1 items-center gap-3 px-4 min-w-0">
          {/* Mobile menu button */}
          <button
            onClick={onToggleSidebar}
            className="p-1.5 rounded-lg hover:bg-muted/30 md:hidden shrink-0"
            aria-label="Toggle navigation"
          >
            <Menu className="h-5 w-5" />
          </button>

          {/* Page title - hidden on very small screens */}
          <h1 className="text-base font-semibold hidden sm:block truncate shrink-0">
            {pageTitle}
          </h1>

          {/* Global Search / Command Palette trigger */}
          <button
            onClick={onOpenPalette}
            className="ml-2 hidden h-8 max-w-sm flex-1 items-center gap-2 rounded-lg border border-border/40 bg-muted/20 px-3 text-sm text-muted-foreground transition-all hover:border-brand/30 hover:bg-muted/30 md:flex group"
            aria-label="Open command palette"
          >
            <Search className="h-3.5 w-3.5 shrink-0 group-hover:text-brand transition-colors" />
            <span className="flex-1 text-left text-xs">Search or jump to...</span>
            <kbd className="flex items-center gap-0.5 rounded border border-border bg-card/80 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground/70">
              <Command className="h-2.5 w-2.5" />K
            </kbd>
          </button>
        </div>

        <div className="flex items-center gap-1 px-3 md:px-4 shrink-0">
          {/* Notifications */}
          <NotificationCenter />

          {/* Quick Scan */}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="hidden h-8 gap-1.5 text-muted-foreground hover:text-foreground sm:flex"
                onClick={() => router.push("/scan/new")}
                aria-label="New scan"
              >
                <ScanSearch className="h-3.5 w-3.5" />
                <span className="text-xs">Scan</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>New Scan</TooltipContent>
          </Tooltip>

          {/* Theme Toggle */}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-muted-foreground hover:text-foreground"
                onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
              >
                <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
                <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              {theme === "dark" ? "Light mode" : "Dark mode"}
            </TooltipContent>
          </Tooltip>

          {/* Separator */}
          <div className="h-5 w-px bg-border/50 mx-1 hidden sm:block" />

          {/* Profile Dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                className="flex items-center gap-2 rounded-lg p-1 transition-colors hover:bg-muted/50"
                aria-label="User menu"
              >
                <Avatar className="h-7 w-7 ring-2 ring-border">
                  <AvatarFallback className="bg-gradient-to-br from-brand/20 to-brand-2/20 text-[10px] font-semibold text-brand">
                    {getInitials()}
                  </AvatarFallback>
                </Avatar>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              <div className="px-2.5 py-2">
                <p className="text-sm font-medium">{user?.full_name || "User"}</p>
                <p className="text-xs text-muted-foreground">{user?.email}</p>
              </div>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => router.push("/settings")} className="text-sm cursor-pointer">
                Settings
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={logout}
                className="text-destructive focus:bg-destructive/10 focus:text-destructive cursor-pointer"
              >
                Log out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>
    </TooltipProvider>
  );
}
