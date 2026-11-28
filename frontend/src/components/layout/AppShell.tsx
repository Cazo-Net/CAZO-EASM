"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { CommandPalette } from "@/components/layout/CommandPalette";
import { SupportChat } from "@/components/support/SupportChat";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const handleToggleMobile = useCallback(() => {
    setMobileOpen((v) => !v);
  }, []);

  const handleCloseMobile = useCallback(() => {
    setMobileOpen(false);
  }, []);

  if (!isAuthenticated) {
    return <>{children}</>;
  }

  return (
    <>
      {/* Fixed background - never moves, never scrolls */}
      <div className="app-background" aria-hidden="true" />

      {/* Application shell - viewport locked */}
      <div className="app-shell">
        {/* Mobile overlay */}
        {mobileOpen && (
          <div
            className="fixed inset-0 z-40 bg-black/50 md:hidden"
            onClick={handleCloseMobile}
            aria-hidden="true"
          />
        )}

        {/* Sidebar - fixed, never scrolls */}
        <div
          className={`fixed inset-y-0 left-0 z-50 transition-transform duration-300 md:static md:translate-x-0 ${
            mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
          }`}
        >
          <Sidebar
            collapsed={sidebarCollapsed}
            onCollapsedChange={setSidebarCollapsed}
          />
        </div>

        {/* Main content area */}
        <div className="app-content">
          {/* TopBar - fixed within the content area */}
          <TopBar
            sidebarCollapsed={sidebarCollapsed}
            onToggleSidebar={handleToggleMobile}
            onOpenPalette={() => setPaletteOpen(true)}
          />

          {/* Scrollable content - only this area scrolls */}
          <div className="app-content-scroll">
            <div className="page-transition">
              {children}
            </div>
          </div>
        </div>

        {/* Command Palette */}
        <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />

        {/* Support Chat Widget */}
        <SupportChat />
      </div>
    </>
  );
}
