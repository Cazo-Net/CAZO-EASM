"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import {
  Search,
  ScanSearch,
  Sun,
  Moon,
  Menu,
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

const routeTitles: Record<string, string> = {
  "/": "AttackSec",
  "/dashboard": "Dashboard",
  "/scans": "Scans",
  "/assets": "Assets",
  "/reports": "Reports",
  "/settings": "Settings",
  "/vulnerabilities": "Vulnerabilities",
  "/dns": "DNS Records",
  "/whois": "WHOIS Records",
  "/graph": "Attack Graph",
  "/scan/new": "New Scan",
  "/compare": "Compare Scans",
  "/ai": "AI Intelligence",
  "/ai/copilot": "AI Copilot",
  "/ai/knowledge": "Knowledge Center",
  "/ai/recommendations": "Recommendations",
  "/ai/settings": "AI Settings",
  "/canvas": "Intelligence Canvas",
};

interface TopBarProps {
  sidebarCollapsed: boolean;
  onToggleSidebar?: () => void;
}

export function TopBar({ sidebarCollapsed, onToggleSidebar }: TopBarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const [searchQuery, setSearchQuery] = useState("");

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

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/assets?q=${encodeURIComponent(searchQuery.trim())}`);
    }
  };

  return (
    <header
      className={cn(
        "sticky top-0 z-40 flex h-16 items-center border-b border-border/50 bg-background/80 backdrop-blur-xl transition-all duration-300"
      )}
    >
      <div className="flex flex-1 items-center gap-4 px-4 md:px-6">
        <button
          onClick={onToggleSidebar}
          className="p-1.5 rounded-lg hover:bg-muted/30 md:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>
        <h1 className="text-lg font-semibold hidden sm:block">{pageTitle}</h1>

        <form onSubmit={handleSearch} className="ml-4 hidden max-w-md flex-1 md:flex">
          <div className="relative w-full">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search assets, scans, reports..."
              className="h-9 w-full rounded-lg border border-border/50 bg-muted/30 pl-9 pr-4 text-sm text-foreground placeholder:text-muted-foreground/60 transition-colors focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/30"
            />
          </div>
        </form>
      </div>

      <div className="flex items-center gap-2 px-4 md:px-6">
        <NotificationCenter />

        <Button
          variant="ghost"
          size="sm"
          className="hidden h-9 gap-2 text-muted-foreground hover:text-foreground sm:flex"
          onClick={() => router.push("/scan/new")}
        >
          <ScanSearch className="h-4 w-4" />
          <span>Quick Scan</span>
        </Button>

        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9 text-muted-foreground hover:text-foreground"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center gap-2 rounded-lg p-1.5 transition-colors hover:bg-muted/50">
              <Avatar className="h-8 w-8 ring-2 ring-border">
                <AvatarFallback className="bg-gradient-to-br from-primary/20 to-cyan-400/20 text-xs font-semibold text-primary">
                  {getInitials()}
                </AvatarFallback>
              </Avatar>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <div className="px-2 py-1.5">
              <p className="text-sm font-medium">{user?.full_name || "User"}</p>
              <p className="text-xs text-muted-foreground">{user?.email}</p>
            </div>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => router.push("/settings")} className="text-sm">
              Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={logout} className="text-destructive focus:bg-destructive/10 focus:text-destructive">
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
