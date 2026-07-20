"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Bell,
  Check,
  CheckCheck,
  Trash2,
  Globe,
  Lock,
  Shield,
  AlertTriangle,
  Activity,
  Scan,
  X,
  Loader2,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import {
  listNotifications,
  getUnreadCount,
  markNotificationRead,
  markAllNotificationsRead,
  deleteNotification,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface Notification {
  id: string;
  type: string;
  title: string;
  message: string;
  data: Record<string, any>;
  read: boolean;
  created_at: string;
}

const typeConfig: Record<string, { icon: any; color: string; bg: string; priority?: string; badge?: string }> = {
  scan_completed: { icon: Check, color: "text-emerald-400", bg: "bg-emerald-500/10", badge: "Scan" },
  scan_failed: { icon: X, color: "text-red-400", bg: "bg-red-500/10", priority: "high", badge: "Scan" },
  ssl_expiring: { icon: Lock, color: "text-amber-400", bg: "bg-amber-500/10", priority: "normal", badge: "Cert" },
  new_shadow_asset: { icon: Globe, color: "text-blue-400", bg: "bg-blue-500/10", badge: "Asset" },
  new_finding_critical: { icon: AlertTriangle, color: "text-red-400", bg: "bg-red-500/10", priority: "critical", badge: "Critical" },
  new_finding_high: { icon: AlertTriangle, color: "text-orange-400", bg: "bg-orange-500/10", priority: "high", badge: "High" },
  new_finding_medium: { icon: AlertTriangle, color: "text-amber-400", bg: "bg-amber-500/10", priority: "normal", badge: "Medium" },
  new_cve_match: { icon: Shield, color: "text-rose-400", bg: "bg-rose-500/10", priority: "high", badge: "CVE" },
  risk_score_changed: { icon: Shield, color: "text-orange-400", bg: "bg-orange-500/10", badge: "Risk" },
  new_asset: { icon: Globe, color: "text-blue-400", bg: "bg-blue-500/10", badge: "Asset" },
  dns_changed: { icon: Activity, color: "text-cyan-400", bg: "bg-cyan-500/10", badge: "DNS" },
  technology_changed: { icon: Scan, color: "text-violet-400", bg: "bg-violet-500/10", badge: "Tech" },
  new_login: { icon: Shield, color: "text-cyan-400", bg: "bg-cyan-500/10", badge: "Auth" },
  password_changed: { icon: Lock, color: "text-amber-400", bg: "bg-amber-500/10", priority: "high", badge: "Auth" },
  email_changed: { icon: Shield, color: "text-amber-400", bg: "bg-amber-500/10", priority: "high", badge: "Auth" },
  weekly_digest: { icon: Activity, color: "text-violet-400", bg: "bg-violet-500/10", badge: "Report" },
};

const priorityBorder: Record<string, string> = {
  critical: "border-l-2 border-l-red-500",
  high: "border-l-2 border-l-orange-400",
  normal: "border-l-2 border-l-amber-400",
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

export function NotificationCenter() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [initialLoaded, setInitialLoaded] = useState(false);

  const fetchUnreadCount = useCallback(async () => {
    try {
      const { count } = await getUnreadCount();
      setUnreadCount(count);
    } catch {
      // silently fail
    }
  }, []);

  const fetchNotifications = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listNotifications({ limit: 20 });
      setNotifications(data.notifications);
      setUnreadCount(data.unread_count);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
      setInitialLoaded(true);
    }
  }, []);

  // Poll unread count every 30 seconds
  useEffect(() => {
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 30000);
    return () => clearInterval(interval);
  }, [fetchUnreadCount]);

  // Fetch full list when opened
  useEffect(() => {
    if (open && !initialLoaded) {
      fetchNotifications();
    }
  }, [open, initialLoaded, fetchNotifications]);

  const handleMarkRead = async (id: string) => {
    try {
      await markNotificationRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, read: true } : n))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch {
      // silently fail
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await markAllNotificationsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
      setUnreadCount(0);
    } catch {
      // silently fail
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteNotification(id);
      setNotifications((prev) => prev.filter((n) => n.id !== id));
      const wasUnread = notifications.find((n) => n.id === id && !n.read);
      if (wasUnread) setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch {
      // silently fail
    }
  };

  const handleClick = (notification: Notification) => {
    if (!notification.read) {
      handleMarkRead(notification.id);
    }
    if (notification.data?.scan_id) {
      router.push(`/scan/${notification.data.scan_id}`);
      setOpen(false);
    }
  };

  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="icon"
        className="relative h-9 w-9 text-muted-foreground hover:text-foreground"
        onClick={() => {
          setOpen(!open);
          if (!open) fetchNotifications();
        }}
      >
        <Bell className="h-4 w-4" />
        {unreadCount > 0 && (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-bold text-primary-foreground">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </Button>

      <AnimatePresence>
        {open && (
          <>
            {/* Backdrop */}
            <div
              className="fixed inset-0 z-40"
              onClick={() => setOpen(false)}
            />

            {/* Panel */}
            <motion.div
              initial={{ opacity: 0, y: -8, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.96 }}
              transition={{ duration: 0.15 }}
              className="absolute right-0 top-full z-50 mt-2 w-[380px] max-h-[500px] rounded-xl border border-border/50 bg-card shadow-2xl shadow-black/30 overflow-hidden"
            >
              {/* Header */}
              <div className="flex items-center justify-between border-b border-border/30 px-4 py-3">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-semibold">Notifications</h3>
                  {unreadCount > 0 && (
                    <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary">
                      {unreadCount} new
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  {unreadCount > 0 && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs gap-1"
                      onClick={handleMarkAllRead}
                    >
                      <CheckCheck className="h-3 w-3" />
                      Read all
                    </Button>
                  )}
                </div>
              </div>

              {/* Notification List */}
              <div className="overflow-y-auto max-h-[400px]">
                {!initialLoaded || (loading && notifications.length === 0) ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                  </div>
                ) : notifications.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <Bell className="h-8 w-8 text-muted-foreground/30 mb-2" />
                    <p className="text-sm text-muted-foreground">No notifications yet</p>
                  </div>
                ) : (
                  <div className="divide-y divide-border/20">
                    {notifications.map((notification) => {
                      const config = typeConfig[notification.type] || typeConfig.scan_completed;
                      const Icon = config.icon;
                      const borderClass = config.priority ? priorityBorder[config.priority] || "" : "";
                      return (
                        <div
                          key={notification.id}
                          className={cn(
                            "group flex items-start gap-3 px-4 py-3 cursor-pointer transition-colors hover:bg-muted/30",
                            !notification.read && "bg-primary/5",
                            borderClass
                          )}
                          onClick={() => handleClick(notification)}
                        >
                          <div className={cn("mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", config.bg)}>
                            <Icon className={cn("h-4 w-4", config.color)} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-start justify-between gap-2">
                              <p className={cn("text-sm leading-tight", !notification.read && "font-medium")}>
                                {notification.title}
                              </p>
                              <div className="flex items-center gap-1.5 shrink-0">
                                {config.badge && (
                                  <span className={cn(
                                    "rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider",
                                    config.priority === "critical" ? "bg-red-500/20 text-red-400" :
                                    config.priority === "high" ? "bg-orange-500/20 text-orange-400" :
                                    "bg-muted text-muted-foreground"
                                  )}>
                                    {config.badge}
                                  </span>
                                )}
                                {!notification.read && (
                                  <div className="h-2 w-2 rounded-full bg-primary" />
                                )}
                              </div>
                            </div>
                            <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                              {notification.message}
                            </p>
                            <p className="text-[10px] text-muted-foreground/60 mt-1">
                              {timeAgo(notification.created_at)}
                            </p>
                          </div>
                          <button
                            className="opacity-0 group-hover:opacity-100 shrink-0 p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-all"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDelete(notification.id);
                            }}
                          >
                            <Trash2 className="h-3 w-3" />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Footer */}
              {notifications.length > 0 && (
                <div className="border-t border-border/30 px-4 py-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full text-xs text-muted-foreground"
                    onClick={() => {
                      setOpen(false);
                      router.push("/settings");
                    }}
                  >
                    Notification settings
                  </Button>
                </div>
              )}
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
