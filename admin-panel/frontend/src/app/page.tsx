"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import api, { getErrorMessage } from "@/lib/api";
import {
  Users, Building, Scan, Database, Server, Activity,
  AlertTriangle, Trash2, Power, PowerOff, Unlock, Key, Search,
  RefreshCw, BarChart3, HardDrive, Cpu, MemoryStick, CheckCircle,
  XCircle, Loader2, LogOut, Globe, Bell, FileText, Fingerprint,
  Flag, Lock, Clock, Terminal, Eye, Mail, Zap, Settings,
} from "lucide-react";

function CazoMark({ className = "h-7 w-7" }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" fill="none" className={className} aria-hidden="true">
      <defs>
        <linearGradient id="admin-header-gradient" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
          <stop stopColor="#10B981" />
          <stop offset="1" stopColor="#06B6D4" />
        </linearGradient>
      </defs>
      <path
        d="M44.5 12.8A22 22 0 1 0 52 32"
        stroke="url(#admin-header-gradient)"
        strokeWidth="7"
        strokeLinecap="round"
      />
      <circle cx="50" cy="28" r="5" fill="url(#admin-header-gradient)" />
      <circle cx="50" cy="28" r="2" fill="#09090B" />
    </svg>
  );
}

type Tab = "overview" | "users" | "orgs" | "scans" | "vulns" | "assets" | "sessions" | "audit" | "logs" | "notifications" | "apikeys" | "flags" | "database" | "system";

const tabs: { id: Tab; label: string; icon: any }[] = [
  { id: "overview", label: "Overview", icon: BarChart3 },
  { id: "users", label: "Users", icon: Users },
  { id: "orgs", label: "Organizations", icon: Building },
  { id: "scans", label: "Scans", icon: Scan },
  { id: "vulns", label: "Vulnerabilities", icon: AlertTriangle },
  { id: "assets", label: "Assets", icon: Globe },
  { id: "sessions", label: "Sessions", icon: Fingerprint },
  { id: "audit", label: "Audit Log", icon: Clock },
  { id: "logs", label: "Logs", icon: Terminal },
  { id: "notifications", label: "Notifications", icon: Bell },
  { id: "apikeys", label: "API Keys", icon: Key },
  { id: "flags", label: "Feature Flags", icon: Flag },
  { id: "database", label: "Database", icon: Database },
  { id: "system", label: "System", icon: Server },
];

export default function AdminPage() {
  const router = useRouter();
  const [authenticated, setAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("overview");
  const [error, setError] = useState("");

  const [stats, setStats] = useState<any>(null);
  const [health, setHealth] = useState<any>(null);
  const [users, setUsers] = useState<any[]>([]);
  const [orgs, setOrgs] = useState<any[]>([]);
  const [scans, setScans] = useState<any[]>([]);
  const [vulns, setVulns] = useState<any[]>([]);
  const [assets, setAssets] = useState<any[]>([]);
  const [sessions, setSessions] = useState<any[]>([]);
  const [auditEvents, setAuditEvents] = useState<any[]>([]);
  const [platformLogs, setPlatformLogs] = useState<any[]>([]);
  const [logSummary, setLogSummary] = useState<any>(null);
  const [logCategory, setLogCategory] = useState("");
  const [logSeverity, setLogSeverity] = useState("");
  const [logSearch, setLogSearch] = useState("");
  const [logHours, setLogHours] = useState<number | "">("");
  const [expandedLog, setExpandedLog] = useState<string | null>(null);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [apiKeys, setApiKeys] = useState<any[]>([]);
  const [featureFlags, setFeatureFlags] = useState<any[]>([]);
  const [dbStats, setDbStats] = useState<any>({});
  const [processes, setProcesses] = useState<any[]>([]);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("");

  // User detail modal
  const [selectedUser, setSelectedUser] = useState<any>(null);
  const [userDetail, setUserDetail] = useState<any>(null);
  const [userForm, setUserForm] = useState({ email: "", full_name: "", role: "" });
  const [newPassword, setNewPassword] = useState("");
  const [userSaving, setUserSaving] = useState(false);
  const [userMsg, setUserMsg] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("admin_token");
    if (!token) { router.push("/login"); return; }
    api.get("/auth/me").then(() => setAuthenticated(true)).catch(() => {
      localStorage.removeItem("admin_token");
      router.push("/login");
    });
  }, [router]);

  const fetchStats = useCallback(async () => {
    try {
      const [s, h] = await Promise.all([api.get("/stats"), api.get("/health")]);
      setStats(s.data); setHealth(h.data);
    } catch (e: any) { setError(getErrorMessage(e)); }
  }, []);

  const fetchUsers = useCallback(async () => {
    try {
      const p: any = { limit: 200 };
      if (search) p.search = search;
      if (filter) p.role = filter;
      setUsers((await api.get("/users", { params: p })).data);
    } catch (e: any) { setError(getErrorMessage(e)); }
  }, [search, filter]);

  const fetchOrgs = useCallback(async () => {
    try { setOrgs((await api.get("/organizations", { params: { limit: 200 } })).data); }
    catch (e: any) { setError(getErrorMessage(e)); }
  }, []);

  const fetchScans = useCallback(async () => {
    try {
      const p: any = { limit: 200 };
      if (filter) p.status = filter;
      setScans((await api.get("/scans", { params: p })).data);
    } catch (e: any) { setError(getErrorMessage(e)); }
  }, [filter]);

  const fetchVulns = useCallback(async () => {
    try {
      const p: any = { limit: 200 };
      if (filter) p.severity = filter;
      setVulns((await api.get("/vulnerabilities", { params: p })).data);
    } catch (e: any) { setError(getErrorMessage(e)); }
  }, [filter]);

  const fetchAssets = useCallback(async () => {
    try {
      const p: any = { limit: 200 };
      if (search) p.search = search;
      if (filter) p.asset_type = filter;
      setAssets((await api.get("/assets", { params: p })).data);
    } catch (e: any) { setError(getErrorMessage(e)); }
  }, [search, filter]);

  const fetchSessions = useCallback(async () => {
    try { setSessions((await api.get("/sessions", { params: { limit: 200 } })).data); }
    catch (e: any) { setError(getErrorMessage(e)); }
  }, []);

  const fetchAudit = useCallback(async () => {
    try { setAuditEvents((await api.get("/audit-events", { params: { limit: 200 } })).data); }
    catch (e: any) { setError(getErrorMessage(e)); }
  }, []);

  const fetchLogSummary = useCallback(async () => {
    try { setLogSummary((await api.get("/platform-logs/summary")).data); }
    catch (e: any) { setError(getErrorMessage(e)); }
  }, []);

  const fetchPlatformLogs = useCallback(async () => {
    try {
      const p: any = { limit: 200 };
      if (logCategory) p.category = logCategory;
      if (logSeverity) p.severity = logSeverity;
      if (logSearch) p.search = logSearch;
      if (logHours) p.hours = logHours;
      setPlatformLogs((await api.get("/platform-logs", { params: p })).data);
    } catch (e: any) { setError(getErrorMessage(e)); }
  }, [logCategory, logSeverity, logSearch, logHours]);

  const fetchNotifications = useCallback(async () => {
    try { setNotifications((await api.get("/notifications", { params: { limit: 200 } })).data); }
    catch (e: any) { setError(getErrorMessage(e)); }
  }, []);

  const fetchApiKeys = useCallback(async () => {
    try { setApiKeys((await api.get("/api-keys", { params: { limit: 200 } })).data); }
    catch (e: any) { setError(getErrorMessage(e)); }
  }, []);

  const fetchFlags = useCallback(async () => {
    try { setFeatureFlags((await api.get("/feature-flags")).data); }
    catch (e: any) { setError(getErrorMessage(e)); }
  }, []);

  const fetchDbStats = useCallback(async () => {
    try { setDbStats((await api.get("/database/stats")).data); }
    catch (e: any) { setError(getErrorMessage(e)); }
  }, []);

  const fetchProcesses = useCallback(async () => {
    try { setProcesses((await api.get("/system/processes")).data); }
    catch (e: any) { setError(getErrorMessage(e)); }
  }, []);

  const openUserDetail = async (user: any) => {
    setSelectedUser(user);
    setUserMsg("");
    setNewPassword("");
    setUserForm({ email: user.email, full_name: user.full_name || "", role: user.role });
    try {
      const r = await api.get(`/users/${user.id}`);
      setUserDetail(r.data);
    } catch (e: any) { setError(getErrorMessage(e)); }
  };

  const saveUserProfile = async () => {
    if (!selectedUser) return;
    setUserSaving(true);
    setUserMsg("");
    try {
      const r = await api.put(`/users/${selectedUser.id}/profile`, userForm);
      setUserMsg(r.data.message);
      fetchUsers();
    } catch (e: any) { setUserMsg(getErrorMessage(e)); }
    finally { setUserSaving(false); }
  };

  const resetUserPassword = async () => {
    if (!selectedUser || !newPassword) return;
    setUserSaving(true);
    setUserMsg("");
    try {
      const r = await api.post(`/users/${selectedUser.id}/reset-password`, { new_password: newPassword });
      setUserMsg(r.data.message);
      setNewPassword("");
    } catch (e: any) { setUserMsg(getErrorMessage(e)); }
    finally { setUserSaving(false); }
  };

  const toggleUserMfa = async (enforced: boolean) => {
    if (!selectedUser) return;
    setUserSaving(true);
    setUserMsg("");
    try {
      const r = await api.put(`/users/${selectedUser.id}/mfa?enforced=${enforced}`);
      setUserMsg(r.data.message);
      setUserDetail((d: any) => ({ ...d, mfa_enforced: enforced }));
      fetchUsers();
    } catch (e: any) { setUserMsg(getErrorMessage(e)); }
    finally { setUserSaving(false); }
  };

  useEffect(() => {
    if (authenticated) { setLoading(true); fetchStats().finally(() => setLoading(false)); }
  }, [authenticated, fetchStats]);

  useEffect(() => {
    if (!authenticated) return;
    setSearch(""); setFilter("");
    if (tab === "users") fetchUsers();
    if (tab === "orgs") fetchOrgs();
    if (tab === "scans") fetchScans();
    if (tab === "vulns") fetchVulns();
    if (tab === "assets") fetchAssets();
    if (tab === "sessions") fetchSessions();
    if (tab === "audit") fetchAudit();
    if (tab === "logs") { fetchLogSummary(); fetchPlatformLogs(); }
    if (tab === "notifications") fetchNotifications();
    if (tab === "apikeys") fetchApiKeys();
    if (tab === "flags") fetchFlags();
    if (tab === "database") fetchDbStats();
    if (tab === "system") fetchProcesses();
  }, [tab, authenticated]);

  const doAction = async (key: string, fn: () => Promise<any>, refresh?: () => void) => {
    setActionLoading(key);
    try {
      await fn();
      refresh?.();
      if (tab === "overview") fetchStats();
    } catch (e: any) { setError(getErrorMessage(e)); }
    finally { setActionLoading(null); }
  };

  const logout = () => { localStorage.removeItem("admin_token"); router.push("/login"); };

  if (!authenticated || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  const fmtTime = (s: number) => {
    const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
    return d > 0 ? `${d}d ${h}h` : h > 0 ? `${h}h ${m}m` : `${m}m`;
  };

  const fmtDate = (s: string) => {
    if (!s || s === "None") return "—";
    try { return new Date(s).toLocaleDateString(); } catch { return "—"; }
  };

  const severityColor = (s: string) => ({
    critical: "text-red-500 bg-red-500/10", high: "text-orange-500 bg-orange-500/10",
    medium: "text-yellow-500 bg-yellow-500/10", low: "text-blue-500 bg-blue-500/10",
    info: "text-zinc-400 bg-zinc-500/10",
  }[s] || "text-zinc-400 bg-zinc-500/10");

  const statusColor = (s: string) => ({
    completed: "bg-green-500", running: "bg-blue-500 animate-pulse",
    failed: "bg-red-500", pending: "bg-yellow-500",
    open: "bg-red-500", confirmed: "bg-orange-500", fixed: "bg-green-500",
    active: "bg-green-500", inactive: "bg-zinc-500",
  }[s] || "bg-zinc-500");

  return (
    <div className="min-h-screen p-6 max-w-[1600px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <CazoMark className="h-7 w-7" />
          <div>
            <h1 className="text-xl font-bold">CAZO Admin Panel</h1>
            <p className="text-xs text-zinc-500">Standalone control console &mdash; Backend :9000 / Frontend :3001</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-xs text-zinc-600 mr-2">Uptime: {health ? fmtTime(health.uptime_seconds) : "—"}</div>
          <button onClick={() => fetchStats()} className="px-3 py-1.5 rounded-lg bg-zinc-800 border border-zinc-700 text-sm hover:bg-zinc-700 flex items-center gap-1.5">
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </button>
          <button onClick={logout} className="px-3 py-1.5 rounded-lg bg-zinc-800 border border-zinc-700 text-sm hover:bg-zinc-700 flex items-center gap-1.5">
            <LogOut className="h-3.5 w-3.5" /> Logout
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex justify-between">
          <span>{error}</span>
          <button onClick={() => setError("")}><XCircle className="h-4 w-4" /></button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-zinc-800 pb-1 overflow-x-auto">
        {tabs.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${tab === t.id ? "bg-blue-500/10 text-blue-400" : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"}`}>
            <t.icon className="h-4 w-4" /> {t.label}
          </button>
        ))}
      </div>

      {/* ── OVERVIEW ─────────────────────────────────────────── */}
      {tab === "overview" && stats && health && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {[
              { l: "Users", v: stats.users_total, i: Users, c: "text-blue-400", s: `${stats.users_active} active / ${stats.users_locked} locked` },
              { l: "Organizations", v: stats.orgs_total, i: Building, c: "text-purple-400", s: `${stats.orgs_active} active` },
              { l: "Scans", v: stats.scans_total, i: Scan, c: "text-cyan-400", s: `${stats.scans_running} running / ${stats.scans_failed} failed` },
              { l: "Vulnerabilities", v: stats.vulns_total, i: AlertTriangle, c: "text-red-400", s: `${stats.vulns_critical} critical / ${stats.vulns_high} high` },
              { l: "Assets", v: stats.assets_total, i: Globe, c: "text-green-400", s: `${stats.subdomains_total} subdomains` },
              { l: "DB Size", v: `${stats.db_size_mb} MB`, i: Database, c: "text-amber-400", s: `${stats.api_keys_total} API keys` },
            ].map((x) => (
              <div key={x.l} className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-zinc-500 uppercase">{x.l}</span>
                  <x.i className={`h-4 w-4 ${x.c}`} />
                </div>
                <div className="text-2xl font-bold">{x.v}</div>
                {x.s && <div className="text-xs text-zinc-500 mt-1">{x.s}</div>}
              </div>
            ))}
          </div>

          {/* Vuln breakdown + Scans breakdown side by side */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
              <h2 className="text-lg font-semibold mb-4">Vulnerability Breakdown</h2>
              <div className="grid grid-cols-5 gap-3">
                {[
                  { l: "Critical", v: stats.vulns_critical, c: "text-red-500" },
                  { l: "High", v: stats.vulns_high, c: "text-orange-500" },
                  { l: "Medium", v: stats.vulns_medium, c: "text-yellow-500" },
                  { l: "Low", v: stats.vulns_low, c: "text-blue-500" },
                  { l: "Info", v: stats.vulns_info, c: "text-zinc-400" },
                ].map((x) => (
                  <div key={x.l} className="text-center">
                    <div className={`text-2xl font-bold ${x.c}`}>{x.v}</div>
                    <div className="text-xs text-zinc-500">{x.l}</div>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
              <h2 className="text-lg font-semibold mb-4">Scan Status</h2>
              <div className="grid grid-cols-4 gap-3">
                {[
                  { l: "Running", v: stats.scans_running, c: "text-blue-500" },
                  { l: "Completed", v: stats.scans_completed, c: "text-green-500" },
                  { l: "Failed", v: stats.scans_failed, c: "text-red-500" },
                  { l: "History", v: stats.scan_history_total, c: "text-zinc-400" },
                ].map((x) => (
                  <div key={x.l} className="text-center">
                    <div className={`text-2xl font-bold ${x.c}`}>{x.v}</div>
                    <div className="text-xs text-zinc-500">{x.l}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* System health */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2"><Server className="h-5 w-5" /> System Health</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
              {[
                { l: "Database", v: health.database, ok: health.database === "healthy" },
                { l: "Redis", v: health.redis, ok: health.redis === "healthy" },
                { l: "CPU", v: `${stats.cpu_percent}%`, ok: stats.cpu_percent < 80 },
                { l: "Memory", v: `${stats.memory_used_mb} MB`, ok: stats.memory_percent < 80 },
                { l: "Disk", v: `${health.disk_usage_percent}%`, ok: health.disk_usage_percent < 85 },
                { l: "Load", v: String(health.load_avg_1m), ok: health.load_avg_1m < health.cpu_count },
                { l: "Swap", v: `${health.swap_used_mb} MB`, ok: health.swap_used_mb < 500 },
                { l: "Processes", v: String(health.processes_count), ok: true },
                { l: "CPU Freq", v: `${health.cpu_freq_mhz} MHz`, ok: true },
                { l: "Disk Free", v: `${health.disk_free_gb} GB`, ok: health.disk_free_gb > 5 },
                { l: "Net Sent", v: `${(health.net_bytes_sent / 1048576).toFixed(1)} MB`, ok: true },
                { l: "Net Recv", v: `${(health.net_bytes_recv / 1048576).toFixed(1)} MB`, ok: true },
              ].map((x) => (
                <div key={x.l} className="p-3 rounded-lg bg-zinc-800/50">
                  <div className="text-xs text-zinc-500 mb-1">{x.l}</div>
                  <div className="flex items-center gap-2">
                    {x.ok ? <CheckCircle className="h-3.5 w-3.5 text-green-400" /> : <XCircle className="h-3.5 w-3.5 text-red-400" />}
                    <span className="text-sm font-medium">{x.v}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── USERS ────────────────────────────────────────────── */}
      {tab === "users" && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
              <input value={search} onChange={(e) => setSearch(e.target.value)} onKeyDown={(e) => e.key === "Enter" && fetchUsers()}
                placeholder="Search users..." className="w-full pl-9 pr-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm focus:outline-none focus:border-blue-500" />
            </div>
            <select value={filter} onChange={(e) => setFilter(e.target.value)} className="px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm">
              <option value="">All Roles</option>
              <option value="member">Member</option>
              <option value="admin">Admin</option>
              <option value="superuser">Superuser</option>
            </select>
            <button onClick={fetchUsers} className="px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm hover:bg-zinc-700"><RefreshCw className="h-4 w-4" /></button>
          </div>
          <div className="rounded-xl border border-zinc-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-zinc-800/50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">User</th>
                  <th className="text-left px-4 py-3 font-medium">Role</th>
                  <th className="text-left px-4 py-3 font-medium">Status</th>
                  <th className="text-left px-4 py-3 font-medium">MFA</th>
                  <th className="text-left px-4 py-3 font-medium">Failed Logins</th>
                  <th className="text-left px-4 py-3 font-medium">Last Login</th>
                  <th className="text-left px-4 py-3 font-medium">Created</th>
                  <th className="text-right px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-t border-zinc-800 hover:bg-zinc-800/30 cursor-pointer" onClick={() => openUserDetail(u)}>
                    <td className="px-4 py-3">
                      <div className="font-medium">{u.full_name || "—"}</div>
                      <div className="text-xs text-zinc-500">{u.email}</div>
                    </td>
                    <td className="px-4 py-3"><span className={`px-2 py-0.5 rounded text-xs ${u.role === "superuser" ? "bg-purple-500/20 text-purple-400" : u.role === "admin" ? "bg-blue-500/20 text-blue-400" : "bg-zinc-800 border border-zinc-700"}`}>{u.role}</span></td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className={`h-2 w-2 rounded-full ${u.is_active ? "bg-green-500" : "bg-red-500"}`} />
                        <span className="text-xs">{u.is_active ? "Active" : "Disabled"}</span>
                        {u.locked_until && <span className="px-1.5 py-0.5 rounded text-xs bg-red-500/20 text-red-400">Locked</span>}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs ${u.totp_enabled ? "text-green-400" : "text-zinc-500"}`}>{u.totp_enabled ? "TOTP" : "—"}</span>
                      {u.mfa_enforced && <span className="ml-1 text-xs text-amber-400">Enforced</span>}
                    </td>
                    <td className="px-4 py-3"><span className={`text-xs ${u.failed_login_attempts > 0 ? "text-red-400" : "text-zinc-500"}`}>{u.failed_login_attempts}</span></td>
                    <td className="px-4 py-3 text-xs text-zinc-500">{fmtDate(u.last_login)}</td>
                    <td className="px-4 py-3 text-xs text-zinc-500">{fmtDate(u.created_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => doAction(`t-${u.id}`, () => api.put(`/users/${u.id}/${u.is_active ? "disable" : "enable"}`), fetchUsers)}
                          className="p-1.5 rounded hover:bg-zinc-700" title={u.is_active ? "Disable" : "Enable"}>
                          {u.is_active ? <PowerOff className="h-3.5 w-3.5" /> : <Power className="h-3.5 w-3.5" />}
                        </button>
                        {u.locked_until && (
                          <button onClick={() => doAction(`u-${u.id}`, () => api.put(`/users/${u.id}/unlock`), fetchUsers)}
                            className="p-1.5 rounded hover:bg-zinc-700" title="Unlock"><Unlock className="h-3.5 w-3.5" /></button>
                        )}
                        <button onClick={() => doAction(`s-${u.id}`, () => api.delete(`/users/${u.id}/sessions`))}
                          className="p-1.5 rounded hover:bg-zinc-700" title="Revoke sessions"><LogOut className="h-3.5 w-3.5" /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {users.length === 0 && <div className="text-center py-8 text-zinc-500 text-sm">No users found</div>}
          </div>
        </div>
      )}

      {/* ── ORGS ─────────────────────────────────────────────── */}
      {tab === "orgs" && (
        <div className="rounded-xl border border-zinc-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-zinc-800/50">
              <tr>
                <th className="text-left px-4 py-3 font-medium">Organization</th>
                <th className="text-left px-4 py-3 font-medium">Plan</th>
                <th className="text-left px-4 py-3 font-medium">Status</th>
                <th className="text-left px-4 py-3 font-medium">Users</th>
                <th className="text-left px-4 py-3 font-medium">Scans</th>
                <th className="text-left px-4 py-3 font-medium">Projects</th>
                <th className="text-left px-4 py-3 font-medium">MFA</th>
                <th className="text-left px-4 py-3 font-medium">Created</th>
                <th className="text-right px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {orgs.map((o) => (
                <tr key={o.id} className="border-t border-zinc-800 hover:bg-zinc-800/30">
                  <td className="px-4 py-3"><div className="font-medium">{o.name}</div><div className="text-xs text-zinc-500">{o.slug}</div></td>
                  <td className="px-4 py-3"><span className="px-2 py-0.5 rounded text-xs border border-zinc-700">{o.plan}</span></td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className={`h-2 w-2 rounded-full ${o.is_active ? "bg-green-500" : "bg-red-500"}`} />
                      <span className="text-xs">{o.is_active ? "Active" : "Disabled"}</span>
                      {o.is_archived && <span className="px-1.5 py-0.5 rounded text-xs bg-zinc-500/20 text-zinc-400">Archived</span>}
                    </div>
                  </td>
                  <td className="px-4 py-3">{o.user_count}</td>
                  <td className="px-4 py-3">{o.scan_count}</td>
                  <td className="px-4 py-3">{o.project_count}</td>
                  <td className="px-4 py-3">{o.mfa_enforced ? <span className="text-xs text-amber-400">Enforced</span> : <span className="text-xs text-zinc-500">—</span>}</td>
                  <td className="px-4 py-3 text-xs text-zinc-500">{fmtDate(o.created_at)}</td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => doAction(`o-${o.id}`, () => api.put(`/organizations/${o.id}/toggle`), fetchOrgs)}
                      className="p-1.5 rounded hover:bg-zinc-700" title="Toggle">
                      {o.is_active ? <PowerOff className="h-3.5 w-3.5" /> : <Power className="h-3.5 w-3.5" />}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── SCANS ────────────────────────────────────────────── */}
      {tab === "scans" && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <select value={filter} onChange={(e) => setFilter(e.target.value)} className="px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm">
              <option value="">All Status</option>
              <option value="running">Running</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="pending">Pending</option>
            </select>
            <button onClick={fetchScans} className="px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm hover:bg-zinc-700"><RefreshCw className="h-4 w-4" /></button>
          </div>
          <div className="rounded-xl border border-zinc-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-zinc-800/50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">Domain</th>
                  <th className="text-left px-4 py-3 font-medium">Status</th>
                  <th className="text-left px-4 py-3 font-medium">Type</th>
                  <th className="text-left px-4 py-3 font-medium">Progress</th>
                  <th className="text-left px-4 py-3 font-medium">Started</th>
                  <th className="text-left px-4 py-3 font-medium">Completed</th>
                  <th className="text-left px-4 py-3 font-medium">Created</th>
                  <th className="text-right px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {scans.map((s) => (
                  <tr key={s.id} className="border-t border-zinc-800 hover:bg-zinc-800/30">
                    <td className="px-4 py-3 font-mono text-xs">{s.domain}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className={`h-2 w-2 rounded-full ${statusColor(s.status)}`} />
                        <span className="text-xs">{s.status}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3"><span className="px-2 py-0.5 rounded text-xs border border-zinc-700">{s.scan_type}</span></td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-20 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                          <div className="h-full bg-blue-500 rounded-full transition-all" style={{ width: `${s.progress}%` }} />
                        </div>
                        <span className="text-xs text-zinc-500">{s.progress}%</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-zinc-500">{fmtDate(s.started_at)}</td>
                    <td className="px-4 py-3 text-xs text-zinc-500">{fmtDate(s.completed_at)}</td>
                    <td className="px-4 py-3 text-xs text-zinc-500">{fmtDate(s.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      {(s.status === "running" || s.status === "pending") && (
                        <button onClick={() => doAction(`sc-${s.id}`, () => api.delete(`/scans/${s.id}`), fetchScans)}
                          className="p-1.5 rounded hover:bg-red-500/20 text-red-400" title="Cancel"><XCircle className="h-3.5 w-3.5" /></button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── VULNERABILITIES ──────────────────────────────────── */}
      {tab === "vulns" && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <select value={filter} onChange={(e) => setFilter(e.target.value)} className="px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm">
              <option value="">All Severity</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="info">Info</option>
            </select>
            <button onClick={fetchVulns} className="px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm hover:bg-zinc-700"><RefreshCw className="h-4 w-4" /></button>
          </div>
          <div className="rounded-xl border border-zinc-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-zinc-800/50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">Name</th>
                  <th className="text-left px-4 py-3 font-medium">Severity</th>
                  <th className="text-left px-4 py-3 font-medium">Status</th>
                  <th className="text-left px-4 py-3 font-medium">Host</th>
                  <th className="text-left px-4 py-3 font-medium">Type</th>
                  <th className="text-left px-4 py-3 font-medium">First Seen</th>
                  <th className="text-left px-4 py-3 font-medium">Last Seen</th>
                </tr>
              </thead>
              <tbody>
                {vulns.map((v) => (
                  <tr key={v.id} className="border-t border-zinc-800 hover:bg-zinc-800/30">
                    <td className="px-4 py-3"><div className="font-medium max-w-xs truncate">{v.name}</div></td>
                    <td className="px-4 py-3"><span className={`px-2 py-0.5 rounded text-xs font-medium ${severityColor(v.severity)}`}>{v.severity}</span></td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className={`h-2 w-2 rounded-full ${statusColor(v.status)}`} />
                        <span className="text-xs">{v.status}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs max-w-[200px] truncate">{v.host}</td>
                    <td className="px-4 py-3 text-xs text-zinc-500">{v.vuln_type || "—"}</td>
                    <td className="px-4 py-3 text-xs text-zinc-500">{fmtDate(v.first_seen)}</td>
                    <td className="px-4 py-3 text-xs text-zinc-500">{fmtDate(v.last_seen)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {vulns.length === 0 && <div className="text-center py-8 text-zinc-500 text-sm">No vulnerabilities found</div>}
          </div>
        </div>
      )}

      {/* ── ASSETS ───────────────────────────────────────────── */}
      {tab === "assets" && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
              <input value={search} onChange={(e) => setSearch(e.target.value)} onKeyDown={(e) => e.key === "Enter" && fetchAssets()}
                placeholder="Search assets..." className="w-full pl-9 pr-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm focus:outline-none focus:border-blue-500" />
            </div>
            <select value={filter} onChange={(e) => setFilter(e.target.value)} className="px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm">
              <option value="">All Types</option>
              <option value="domain">Domain</option>
              <option value="host">Host</option>
              <option value="ip">IP</option>
              <option value="certificate">Certificate</option>
              <option value="technology">Technology</option>
            </select>
            <button onClick={fetchAssets} className="px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm hover:bg-zinc-700"><RefreshCw className="h-4 w-4" /></button>
          </div>
          <div className="rounded-xl border border-zinc-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-zinc-800/50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">Value</th>
                  <th className="text-left px-4 py-3 font-medium">Type</th>
                  <th className="text-left px-4 py-3 font-medium">Status</th>
                  <th className="text-left px-4 py-3 font-medium">Alive</th>
                  <th className="text-left px-4 py-3 font-medium">Confirmed</th>
                  <th className="text-left px-4 py-3 font-medium">First Seen</th>
                  <th className="text-left px-4 py-3 font-medium">Last Seen</th>
                </tr>
              </thead>
              <tbody>
                {assets.map((a) => (
                  <tr key={a.id} className="border-t border-zinc-800 hover:bg-zinc-800/30">
                    <td className="px-4 py-3 font-mono text-xs max-w-[300px] truncate">{a.value}</td>
                    <td className="px-4 py-3"><span className="px-2 py-0.5 rounded text-xs border border-zinc-700">{a.asset_type}</span></td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className={`h-2 w-2 rounded-full ${statusColor(a.inventory_status)}`} />
                        <span className="text-xs">{a.inventory_status}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">{a.is_alive ? <CheckCircle className="h-3.5 w-3.5 text-green-400" /> : <XCircle className="h-3.5 w-3.5 text-zinc-500" />}</td>
                    <td className="px-4 py-3">{a.confirmed ? <CheckCircle className="h-3.5 w-3.5 text-green-400" /> : <span className="text-xs text-zinc-500">No</span>}</td>
                    <td className="px-4 py-3 text-xs text-zinc-500">{fmtDate(a.first_seen)}</td>
                    <td className="px-4 py-3 text-xs text-zinc-500">{fmtDate(a.last_seen)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {assets.length === 0 && <div className="text-center py-8 text-zinc-500 text-sm">No assets found</div>}
          </div>
        </div>
      )}

      {/* ── SESSIONS ─────────────────────────────────────────── */}
      {tab === "sessions" && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <button onClick={fetchSessions} className="px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm hover:bg-zinc-700 flex items-center gap-1.5"><RefreshCw className="h-3.5 w-3.5" /> Refresh</button>
            <button onClick={() => doAction("revoke-all", () => api.delete("/sessions"), fetchSessions)}
              className="px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-red-400 hover:bg-red-500/20 flex items-center gap-1.5">
              <Trash2 className="h-3.5 w-3.5" /> Revoke All Sessions
            </button>
          </div>
          <div className="rounded-xl border border-zinc-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-zinc-800/50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">User</th>
                  <th className="text-left px-4 py-3 font-medium">Browser / OS</th>
                  <th className="text-left px-4 py-3 font-medium">IP</th>
                  <th className="text-left px-4 py-3 font-medium">Location</th>
                  <th className="text-left px-4 py-3 font-medium">Trusted</th>
                  <th className="text-left px-4 py-3 font-medium">Last Activity</th>
                  <th className="text-right px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => (
                  <tr key={s.id} className="border-t border-zinc-800 hover:bg-zinc-800/30">
                    <td className="px-4 py-3 text-xs font-mono">{s.user_id.slice(0, 8)}...</td>
                    <td className="px-4 py-3"><div className="text-xs">{s.browser || "—"}</div><div className="text-xs text-zinc-500">{s.os || "—"}</div></td>
                    <td className="px-4 py-3 font-mono text-xs">{s.ip_address || "—"}</td>
                    <td className="px-4 py-3 text-xs">{[s.location_city, s.location_country].filter(Boolean).join(", ") || "—"}</td>
                    <td className="px-4 py-3">{s.is_trusted ? <CheckCircle className="h-3.5 w-3.5 text-green-400" /> : <span className="text-xs text-zinc-500">No</span>}</td>
                    <td className="px-4 py-3 text-xs text-zinc-500">{fmtDate(s.last_activity)}</td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => doAction(`rs-${s.id}`, () => api.delete(`/sessions/${s.id}`), fetchSessions)}
                        className="p-1.5 rounded hover:bg-red-500/20 text-red-400" title="Revoke"><Trash2 className="h-3.5 w-3.5" /></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {sessions.length === 0 && <div className="text-center py-8 text-zinc-500 text-sm">No active sessions</div>}
          </div>
        </div>
      )}

      {/* ── AUDIT LOG ────────────────────────────────────────── */}
      {tab === "audit" && (
        <div className="space-y-4">
          <button onClick={fetchAudit} className="px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm hover:bg-zinc-700 flex items-center gap-1.5"><RefreshCw className="h-3.5 w-3.5" /> Refresh</button>
          <div className="rounded-xl border border-zinc-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-zinc-800/50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">Action</th>
                  <th className="text-left px-4 py-3 font-medium">Actor</th>
                  <th className="text-left px-4 py-3 font-medium">Target</th>
                  <th className="text-left px-4 py-3 font-medium">Status</th>
                  <th className="text-left px-4 py-3 font-medium">Time</th>
                </tr>
              </thead>
              <tbody>
                {auditEvents.map((e) => (
                  <tr key={e.id} className="border-t border-zinc-800 hover:bg-zinc-800/30">
                    <td className="px-4 py-3"><span className="px-2 py-0.5 rounded text-xs bg-zinc-800 border border-zinc-700 font-mono">{e.action}</span></td>
                    <td className="px-4 py-3"><span className="text-xs text-zinc-500">{e.actor_type}</span> <span className="text-xs font-mono">{e.actor_id?.slice(0, 8) || "—"}</span></td>
                    <td className="px-4 py-3"><span className="text-xs text-zinc-500">{e.target_type || "—"}</span> <span className="text-xs font-mono">{e.target_id?.slice(0, 8) || ""}</span></td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs ${e.status === "success" ? "text-green-400 bg-green-500/10" : "text-red-400 bg-red-500/10"}`}>{e.status}</span>
                    </td>
                    <td className="px-4 py-3 text-xs text-zinc-500">{fmtDate(e.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {auditEvents.length === 0 && <div className="text-center py-8 text-zinc-500 text-sm">No audit events</div>}
          </div>
        </div>
      )}

      {/* ── PLATFORM LOGS ────────────────────────────────────── */}
      {tab === "logs" && (
        <div className="space-y-4">
          {/* Summary cards */}
          {logSummary && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <button onClick={() => { setLogSeverity("error"); fetchPlatformLogs(); }}
                className="rounded-xl border border-zinc-800 bg-zinc-900 p-4 text-left hover:border-red-500/30 transition-colors">
                <p className="text-2xl font-bold text-red-400 font-mono">{logSummary.errors_24h}</p>
                <p className="text-xs text-zinc-500">Errors (24h)</p>
              </button>
              <button onClick={() => { setLogCategory("security_event"); fetchPlatformLogs(); }}
                className="rounded-xl border border-zinc-800 bg-zinc-900 p-4 text-left hover:border-amber-500/30 transition-colors">
                <p className="text-2xl font-bold text-amber-400 font-mono">{logSummary.security_24h}</p>
                <p className="text-xs text-zinc-500">Security Events (24h)</p>
              </button>
              <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
                <p className="text-2xl font-bold text-zinc-300 font-mono">{logSummary.total_24h}</p>
                <p className="text-xs text-zinc-500">Total Logs (24h)</p>
              </div>
              <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
                <p className="text-2xl font-bold text-blue-400 font-mono">{logSummary.orgs_active_24h}</p>
                <p className="text-xs text-zinc-500">Active Orgs (24h)</p>
              </div>
            </div>
          )}

          {/* Critical events banner */}
          {logSummary?.critical_events?.length > 0 && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4">
              <p className="text-sm font-medium text-red-400 mb-2">Critical Events (last 24h)</p>
              <div className="space-y-1">
                {logSummary.critical_events.map((e: any) => (
                  <div key={e.id} className="flex items-center gap-2 text-xs">
                    <span className="text-zinc-500">{fmtDate(e.created_at)}</span>
                    <span className="text-red-400 font-mono">{e.category}</span>
                    <span className="text-zinc-300 truncate">{e.message}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Top error types */}
          {logSummary?.top_error_types?.length > 0 && (
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
              <p className="text-sm font-medium text-zinc-300 mb-2">Top Error Types (24h)</p>
              <div className="space-y-1">
                {logSummary.top_error_types.map((e: any, i: number) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <span className="text-zinc-400 font-mono truncate max-w-md">{e.message}</span>
                    <span className="text-zinc-500">{e.count}x</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-2">
            <button onClick={() => { fetchLogSummary(); fetchPlatformLogs(); }}
              className="px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm hover:bg-zinc-700 flex items-center gap-1.5">
              <RefreshCw className="h-3.5 w-3.5" /> Refresh
            </button>
            <select value={logCategory} onChange={(e) => setLogCategory(e.target.value)}
              className="px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm text-zinc-300">
              <option value="">All Categories</option>
              <option value="application_error">Application Error</option>
              <option value="scan_event">Scan Event</option>
              <option value="auth_event">Auth Event</option>
              <option value="security_event">Security Event</option>
              <option value="notification">Notification</option>
              <option value="api_request">API Request</option>
              <option value="unexpected">Unexpected</option>
            </select>
            <select value={logSeverity} onChange={(e) => setLogSeverity(e.target.value)}
              className="px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm text-zinc-300">
              <option value="">All Severity</option>
              <option value="info">Info</option>
              <option value="warning">Warning</option>
              <option value="error">Error</option>
              <option value="critical">Critical</option>
            </select>
            <select value={logHours} onChange={(e) => setLogHours(e.target.value ? Number(e.target.value) : "")}
              className="px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm text-zinc-300">
              <option value="">All Time</option>
              <option value="1">Last 1h</option>
              <option value="6">Last 6h</option>
              <option value="24">Last 24h</option>
              <option value="168">Last 7d</option>
              <option value="720">Last 30d</option>
            </select>
            <input value={logSearch} onChange={(e) => setLogSearch(e.target.value)}
              placeholder="Search messages..."
              className="px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm text-zinc-300 w-48" />
            <button onClick={fetchPlatformLogs}
              className="px-3 py-2 rounded-lg bg-blue-500/10 border border-blue-500/20 text-sm text-blue-400 hover:bg-blue-500/20">
              Apply
            </button>
            {(logCategory || logSeverity || logSearch || logHours) && (
              <button onClick={() => { setLogCategory(""); setLogSeverity(""); setLogSearch(""); setLogHours(""); }}
                className="px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm text-zinc-500 hover:text-zinc-300">
                Clear
              </button>
            )}
          </div>

          {/* Log table */}
          <div className="rounded-xl border border-zinc-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-zinc-800/50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium w-2">Severity</th>
                  <th className="text-left px-4 py-3 font-medium">Category</th>
                  <th className="text-left px-4 py-3 font-medium">Message</th>
                  <th className="text-left px-4 py-3 font-medium">Org</th>
                  <th className="text-left px-4 py-3 font-medium">User</th>
                  <th className="text-left px-4 py-3 font-medium">Request</th>
                  <th className="text-left px-4 py-3 font-medium">Time</th>
                </tr>
              </thead>
              <tbody>
                {platformLogs.map((l) => (
                  <React.Fragment key={l.id}>
                    <tr onClick={() => setExpandedLog(expandedLog === l.id ? null : l.id)}
                      className="border-t border-zinc-800 hover:bg-zinc-800/30 cursor-pointer">
                      <td className="px-4 py-3">
                        <span className={`inline-block h-2 w-2 rounded-full ${
                          l.severity === "critical" ? "bg-red-500" :
                          l.severity === "error" ? "bg-orange-500" :
                          l.severity === "warning" ? "bg-amber-500" :
                          "bg-blue-500"
                        }`} />
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded text-xs font-mono ${
                          l.category === "unexpected" ? "bg-red-500/10 text-red-400 border border-red-500/20" :
                          l.category === "security_event" ? "bg-amber-500/10 text-amber-400 border border-amber-500/20" :
                          l.category === "application_error" ? "bg-orange-500/10 text-orange-400 border border-orange-500/20" :
                          "bg-zinc-800 border border-zinc-700 text-zinc-400"
                        }`}>{l.category}</span>
                      </td>
                      <td className="px-4 py-3 text-xs text-zinc-300 max-w-md truncate">{l.message}</td>
                      <td className="px-4 py-3 text-xs font-mono text-zinc-500">{l.organization_id?.slice(0, 8) || "—"}</td>
                      <td className="px-4 py-3 text-xs font-mono text-zinc-500">{l.user_id?.slice(0, 8) || "—"}</td>
                      <td className="px-4 py-3 text-xs font-mono text-zinc-500">{l.request_id?.slice(0, 8) || "—"}</td>
                      <td className="px-4 py-3 text-xs text-zinc-500">{fmtDate(l.created_at)}</td>
                    </tr>
                    {expandedLog === l.id && (
                      <tr className="border-t border-zinc-800 bg-zinc-900/50">
                        <td colSpan={7} className="px-4 py-4">
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs mb-3">
                            <div><span className="text-zinc-500">ID:</span> <span className="font-mono text-zinc-300">{l.id}</span></div>
                            <div><span className="text-zinc-500">Client IP:</span> <span className="font-mono text-zinc-300">{l.client_ip || "—"}</span></div>
                            <div><span className="text-zinc-500">Method:</span> <span className="font-mono text-zinc-300">{l.method || "—"}</span></div>
                            <div><span className="text-zinc-500">Path:</span> <span className="font-mono text-zinc-300">{l.path || "—"}</span></div>
                            <div><span className="text-zinc-500">Status:</span> <span className="font-mono text-zinc-300">{l.status_code || "—"}</span></div>
                            <div><span className="text-zinc-500">Duration:</span> <span className="font-mono text-zinc-300">{l.duration_ms ? `${l.duration_ms}ms` : "—"}</span></div>
                            <div><span className="text-zinc-500">Entity:</span> <span className="font-mono text-zinc-300">{l.related_entity_type ? `${l.related_entity_type}/${l.related_entity_id}` : "—"}</span></div>
                          </div>
                          {l.detail && Object.keys(l.detail).length > 0 && (
                            <div className="rounded-lg bg-zinc-950 border border-zinc-800 p-3">
                              <p className="text-xs text-zinc-500 mb-1">Detail</p>
                              <pre className="text-xs text-zinc-400 font-mono overflow-x-auto whitespace-pre-wrap max-h-64 overflow-y-auto">
                                {JSON.stringify(l.detail, null, 2)}
                              </pre>
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
            {platformLogs.length === 0 && <div className="text-center py-8 text-zinc-500 text-sm">No logs found</div>}
          </div>
        </div>
      )}

      {/* ── NOTIFICATIONS ────────────────────────────────────── */}
      {tab === "notifications" && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <button onClick={fetchNotifications} className="px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm hover:bg-zinc-700 flex items-center gap-1.5"><RefreshCw className="h-3.5 w-3.5" /> Refresh</button>
            <button onClick={() => doAction("mark-all", () => api.put("/notifications/mark-all-read"), fetchNotifications)}
              className="px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm hover:bg-zinc-700 flex items-center gap-1.5"><CheckCircle className="h-3.5 w-3.5" /> Mark All Read</button>
          </div>
          <div className="rounded-xl border border-zinc-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-zinc-800/50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">Title</th>
                  <th className="text-left px-4 py-3 font-medium">Type</th>
                  <th className="text-left px-4 py-3 font-medium">Priority</th>
                  <th className="text-left px-4 py-3 font-medium">Channel</th>
                  <th className="text-left px-4 py-3 font-medium">Read</th>
                  <th className="text-left px-4 py-3 font-medium">Time</th>
                  <th className="text-right px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {notifications.map((n) => (
                  <tr key={n.id} className={`border-t border-zinc-800 hover:bg-zinc-800/30 ${!n.read ? "bg-blue-500/5" : ""}`}>
                    <td className="px-4 py-3"><div className="font-medium text-xs">{n.title}</div><div className="text-xs text-zinc-500 max-w-xs truncate">{n.message}</div></td>
                    <td className="px-4 py-3"><span className="px-2 py-0.5 rounded text-xs border border-zinc-700">{n.type}</span></td>
                    <td className="px-4 py-3"><span className={`px-2 py-0.5 rounded text-xs ${n.priority === "critical" ? "text-red-400 bg-red-500/10" : n.priority === "high" ? "text-orange-400 bg-orange-500/10" : "bg-zinc-800"}`}>{n.priority}</span></td>
                    <td className="px-4 py-3 text-xs">{n.channel}</td>
                    <td className="px-4 py-3">{n.read ? <CheckCircle className="h-3.5 w-3.5 text-green-400" /> : <XCircle className="h-3.5 w-3.5 text-zinc-500" />}</td>
                    <td className="px-4 py-3 text-xs text-zinc-500">{fmtDate(n.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      {!n.read && (
                        <button onClick={() => doAction(`nr-${n.id}`, () => api.put(`/notifications/${n.id}/read`), fetchNotifications)}
                          className="p-1.5 rounded hover:bg-zinc-700" title="Mark read"><Eye className="h-3.5 w-3.5" /></button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {notifications.length === 0 && <div className="text-center py-8 text-zinc-500 text-sm">No notifications</div>}
          </div>
        </div>
      )}

      {/* ── API KEYS ─────────────────────────────────────────── */}
      {tab === "apikeys" && (
        <div className="space-y-4">
          <button onClick={fetchApiKeys} className="px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm hover:bg-zinc-700 flex items-center gap-1.5"><RefreshCw className="h-3.5 w-3.5" /> Refresh</button>
          <div className="rounded-xl border border-zinc-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-zinc-800/50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">Name</th>
                  <th className="text-left px-4 py-3 font-medium">Prefix</th>
                  <th className="text-left px-4 py-3 font-medium">User</th>
                  <th className="text-left px-4 py-3 font-medium">Status</th>
                  <th className="text-left px-4 py-3 font-medium">Last Used</th>
                  <th className="text-left px-4 py-3 font-medium">Created</th>
                  <th className="text-left px-4 py-3 font-medium">Expires</th>
                  <th className="text-right px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {apiKeys.map((k) => (
                  <tr key={k.id} className="border-t border-zinc-800 hover:bg-zinc-800/30">
                    <td className="px-4 py-3 font-medium text-xs">{k.name}</td>
                    <td className="px-4 py-3 font-mono text-xs text-zinc-500">{k.prefix}...</td>
                    <td className="px-4 py-3 text-xs font-mono">{k.user_id.slice(0, 8)}...</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className={`h-2 w-2 rounded-full ${k.is_active ? "bg-green-500" : "bg-red-500"}`} />
                        <span className="text-xs">{k.is_active ? "Active" : "Revoked"}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-zinc-500">{fmtDate(k.last_used_at)}</td>
                    <td className="px-4 py-3 text-xs text-zinc-500">{fmtDate(k.created_at)}</td>
                    <td className="px-4 py-3 text-xs text-zinc-500">{fmtDate(k.expires_at)}</td>
                    <td className="px-4 py-3 text-right">
                      {k.is_active && (
                        <button onClick={() => doAction(`rk-${k.id}`, () => api.delete(`/api-keys/${k.id}`), fetchApiKeys)}
                          className="p-1.5 rounded hover:bg-red-500/20 text-red-400" title="Revoke"><Trash2 className="h-3.5 w-3.5" /></button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {apiKeys.length === 0 && <div className="text-center py-8 text-zinc-500 text-sm">No API keys</div>}
          </div>
        </div>
      )}

      {/* ── FEATURE FLAGS ────────────────────────────────────── */}
      {tab === "flags" && (
        <div className="space-y-4">
          <button onClick={fetchFlags} className="px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm hover:bg-zinc-700 flex items-center gap-1.5"><RefreshCw className="h-3.5 w-3.5" /> Refresh</button>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {featureFlags.map((f) => (
              <div key={f.id} className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-sm font-medium">{f.key}</span>
                  <button onClick={() => doAction(`ff-${f.id}`, () => api.put(`/feature-flags/${f.id}/toggle`), fetchFlags)}
                    className={`px-2 py-0.5 rounded text-xs font-medium ${f.enabled ? "bg-green-500/20 text-green-400" : "bg-zinc-700 text-zinc-400"}`}>
                    {f.enabled ? "ON" : "OFF"}
                  </button>
                </div>
                <div className="text-sm font-medium mb-1">{f.name}</div>
                {f.description && <div className="text-xs text-zinc-500 mb-2">{f.description}</div>}
                {f.allowed_plans && f.allowed_plans.length > 0 && (
                  <div className="flex gap-1 flex-wrap">
                    {f.allowed_plans.map((p: string) => <span key={p} className="px-1.5 py-0.5 rounded text-xs bg-zinc-800 border border-zinc-700">{p}</span>)}
                  </div>
                )}
              </div>
            ))}
          </div>
          {featureFlags.length === 0 && <div className="text-center py-8 text-zinc-500 text-sm">No feature flags</div>}
        </div>
      )}

      {/* ── DATABASE ─────────────────────────────────────────── */}
      {tab === "database" && (
        <div className="space-y-6">
          <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Table Row Counts</h2>
              <button onClick={fetchDbStats} className="px-3 py-1.5 rounded-lg bg-zinc-800 border border-zinc-700 text-sm hover:bg-zinc-700 flex items-center gap-1.5">
                <RefreshCw className="h-3.5 w-3.5" /> Refresh
              </button>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
              {Object.entries(dbStats).sort(([, a], [b]) => Number(b) - Number(a)).map(([table, count]) => (
                <div key={table} className="flex items-center justify-between p-3 rounded-lg bg-zinc-800/50">
                  <span className="text-sm font-mono truncate mr-2">{table}</span>
                  <span className="px-2 py-0.5 rounded text-xs bg-zinc-800 border border-zinc-700 whitespace-nowrap">
                    {count === -1 ? "N/A" : (count as number).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── SYSTEM ───────────────────────────────────────────── */}
      {tab === "system" && (
        <div className="space-y-6">
          {health && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { l: "CPU Cores", v: health.cpu_count, i: Cpu },
                { l: "CPU Freq", v: `${health.cpu_freq_mhz} MHz`, i: Cpu },
                { l: "Memory", v: `${Math.round(health.memory_total_mb / 1024)} GB`, i: MemoryStick },
                { l: "Swap", v: `${health.swap_total_mb} MB`, i: MemoryStick },
                { l: "Disk Free", v: `${health.disk_free_gb} GB`, i: HardDrive },
                { l: "Processes", v: String(health.processes_count), i: Terminal },
                { l: "Uptime", v: fmtTime(health.uptime_seconds), i: Clock },
                { l: "Load Avg", v: String(health.load_avg_1m), i: Activity },
              ].map((x) => (
                <div key={x.l} className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-zinc-500 uppercase">{x.l}</span>
                    <x.i className="h-4 w-4 text-zinc-500" />
                  </div>
                  <div className="text-xl font-bold">{x.v}</div>
                </div>
              ))}
            </div>
          )}

          <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold flex items-center gap-2"><Terminal className="h-5 w-5" /> Top Processes (by memory)</h2>
              <button onClick={fetchProcesses} className="px-3 py-1.5 rounded-lg bg-zinc-800 border border-zinc-700 text-sm hover:bg-zinc-700 flex items-center gap-1.5"><RefreshCw className="h-3.5 w-3.5" /> Refresh</button>
            </div>
            <div className="rounded-xl border border-zinc-800 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-zinc-800/50">
                  <tr>
                    <th className="text-left px-4 py-2 font-medium">PID</th>
                    <th className="text-left px-4 py-2 font-medium">Name</th>
                    <th className="text-left px-4 py-2 font-medium">CPU %</th>
                    <th className="text-left px-4 py-2 font-medium">Memory</th>
                    <th className="text-left px-4 py-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {processes.slice(0, 30).map((p) => (
                    <tr key={p.pid} className="border-t border-zinc-800 hover:bg-zinc-800/30">
                      <td className="px-4 py-2 font-mono text-xs">{p.pid}</td>
                      <td className="px-4 py-2 text-xs font-medium max-w-[200px] truncate">{p.name}</td>
                      <td className="px-4 py-2 text-xs">{p.cpu_percent.toFixed(1)}%</td>
                      <td className="px-4 py-2 text-xs">{p.memory_mb} MB</td>
                      <td className="px-4 py-2"><span className={`px-2 py-0.5 rounded text-xs ${p.status === "running" ? "text-green-400 bg-green-500/10" : "bg-zinc-800"}`}>{p.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {health && (
            <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
              <h2 className="text-lg font-semibold mb-4">Configuration</h2>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {[
                  { l: "SQLite Mode", v: health.use_sqlite ? "Yes" : "No" },
                  { l: "DB Pool Size", v: String(health.database_pool_size) },
                  { l: "DB Active Conns", v: String(health.database_pool_checked_out) },
                  { l: "Disk Usage", v: `${health.disk_usage_percent}%` },
                  { l: "Environment", v: health.env },
                  { l: "Net Sent", v: `${(health.net_bytes_sent / 1048576).toFixed(1)} MB` },
                  { l: "Net Recv", v: `${(health.net_bytes_recv / 1048576).toFixed(1)} MB` },
                ].map((x) => (
                  <div key={x.l} className="flex items-center justify-between p-2 rounded bg-zinc-800/30">
                    <span className="text-xs text-zinc-500">{x.l}</span>
                    <span className="text-sm font-medium">{x.v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── USER DETAIL MODAL ─────────────────────────────────── */}
      {selectedUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setSelectedUser(null)}>
          <div className="bg-zinc-900 border border-zinc-700 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-full bg-blue-500/20 flex items-center justify-center text-blue-400 font-bold text-lg">
                  {(userDetail?.full_name || selectedUser.email)?.[0]?.toUpperCase() || "?"}
                </div>
                <div>
                  <h2 className="text-lg font-bold">{userDetail?.full_name || "No name"}</h2>
                  <p className="text-xs text-zinc-500">{selectedUser.email}</p>
                </div>
              </div>
              <button onClick={() => setSelectedUser(null)} className="p-2 rounded-lg hover:bg-zinc-800"><XCircle className="h-5 w-5" /></button>
            </div>

            {userMsg && (
              <div className={`mb-4 p-3 rounded-lg text-sm ${userMsg.includes("success") || userMsg.includes("updated") || userMsg.includes("Password") || userMsg.includes("MFA") ? "bg-green-500/10 border border-green-500/20 text-green-400" : "bg-red-500/10 border border-red-500/20 text-red-400"}`}>
                {userMsg}
              </div>
            )}

            {/* Stats */}
            {userDetail && (
              <div className="grid grid-cols-4 gap-3 mb-6">
                {[
                  { l: "Sessions", v: userDetail.session_count },
                  { l: "Scans", v: userDetail.scan_count },
                  { l: "API Keys", v: userDetail.api_key_count },
                  { l: "Failed Logins", v: userDetail.failed_login_attempts },
                ].map((x) => (
                  <div key={x.l} className="p-3 rounded-lg bg-zinc-800/50 text-center">
                    <div className="text-xl font-bold">{x.v}</div>
                    <div className="text-xs text-zinc-500">{x.l}</div>
                  </div>
                ))}
              </div>
            )}

            {/* Profile Edit */}
            <div className="mb-6">
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2"><Users className="h-4 w-4" /> Profile</h3>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-zinc-500 mb-1">Full Name</label>
                  <input value={userForm.full_name} onChange={(e) => setUserForm({ ...userForm, full_name: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm focus:outline-none focus:border-blue-500" />
                </div>
                <div>
                  <label className="block text-xs text-zinc-500 mb-1">Email</label>
                  <input value={userForm.email} onChange={(e) => setUserForm({ ...userForm, email: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm focus:outline-none focus:border-blue-500" />
                </div>
                <div>
                  <label className="block text-xs text-zinc-500 mb-1">Role</label>
                  <select value={userForm.role} onChange={(e) => setUserForm({ ...userForm, role: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm">
                    <option value="member">Member</option>
                    <option value="admin">Admin</option>
                    <option value="superuser">Superuser</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-zinc-500 mb-1">Status</label>
                  <div className="flex items-center gap-2 h-[38px]">
                    <span className={`h-2.5 w-2.5 rounded-full ${selectedUser.is_active ? "bg-green-500" : "bg-red-500"}`} />
                    <span className="text-sm">{selectedUser.is_active ? "Active" : "Disabled"}</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 mt-3">
                <button onClick={saveUserProfile} disabled={userSaving}
                  className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium disabled:opacity-50 flex items-center gap-2">
                  {userSaving && <Loader2 className="h-3.5 w-3.5 animate-spin" />} Save Profile
                </button>
                <button onClick={() => doAction(`t-${selectedUser.id}`, () => api.put(`/users/${selectedUser.id}/${selectedUser.is_active ? "disable" : "enable"}`), () => { fetchUsers(); openUserDetail({ ...selectedUser, is_active: !selectedUser.is_active }); })}
                  className={`px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 ${selectedUser.is_active ? "bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20" : "bg-green-500/10 border border-green-500/20 text-green-400 hover:bg-green-500/20"}`}>
                  {selectedUser.is_active ? <><PowerOff className="h-3.5 w-3.5" /> Disable</> : <><Power className="h-3.5 w-3.5" /> Enable</>}
                </button>
                {selectedUser.locked_until && (
                  <button onClick={() => doAction(`u-${selectedUser.id}`, () => api.put(`/users/${selectedUser.id}/unlock`), () => { fetchUsers(); openUserDetail({ ...selectedUser, locked_until: null }); })}
                    className="px-4 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 text-sm font-medium flex items-center gap-2 hover:bg-amber-500/20">
                    <Unlock className="h-3.5 w-3.5" /> Unlock
                  </button>
                )}
                <button onClick={() => doAction(`s-${selectedUser.id}`, () => api.delete(`/users/${selectedUser.id}/sessions`))}
                  className="px-4 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm hover:bg-zinc-700 flex items-center gap-2">
                  <LogOut className="h-3.5 w-3.5" /> Revoke Sessions
                </button>
              </div>
            </div>

            {/* Password Reset */}
            <div className="mb-6">
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2"><Lock className="h-4 w-4" /> Reset Password</h3>
              <div className="flex items-center gap-2">
                <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Enter new password (min 8 chars)" className="flex-1 px-3 py-2 rounded-lg bg-zinc-800 border border-zinc-700 text-sm focus:outline-none focus:border-blue-500" />
                <button onClick={resetUserPassword} disabled={userSaving || !newPassword || newPassword.length < 8}
                  className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-sm font-medium disabled:opacity-50 flex items-center gap-2">
                  {userSaving && <Loader2 className="h-3.5 w-3.5 animate-spin" />} Reset
                </button>
              </div>
              <p className="text-xs text-zinc-600 mt-1.5">This will hash the new password, revoke all sessions, and increment token version.</p>
            </div>

            {/* MFA */}
            <div className="mb-6">
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2"><Fingerprint className="h-4 w-4" /> Multi-Factor Authentication</h3>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <span className={`h-2.5 w-2.5 rounded-full ${userDetail?.mfa_enforced ? "bg-green-500" : "bg-zinc-500"}`} />
                  <span className="text-sm">{userDetail?.mfa_enforced ? "MFA Enforced" : "MFA Not Enforced"}</span>
                </div>
                <button onClick={() => toggleUserMfa(!userDetail?.mfa_enforced)} disabled={userSaving}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium ${userDetail?.mfa_enforced ? "bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20" : "bg-green-500/10 border border-green-500/20 text-green-400 hover:bg-green-500/20"}`}>
                  {userDetail?.mfa_enforced ? "Remove Enforcement" : "Enforce MFA"}
                </button>
              </div>
              <div className="mt-2 text-xs text-zinc-500">
                TOTP: {userDetail?.totp_enabled ? <span className="text-green-400">Enabled</span> : <span className="text-zinc-500">Not set up</span>}
              </div>
            </div>

            {/* Info */}
            {userDetail && (
              <div>
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-2"><Clock className="h-4 w-4" /> Details</h3>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { l: "User ID", v: userDetail.id },
                    { l: "Organization", v: userDetail.organization_name || "None" },
                    { l: "Created", v: fmtDate(userDetail.created_at) },
                    { l: "Last Login", v: fmtDate(userDetail.last_login) },
                    { l: "Password Changed", v: fmtDate(userDetail.password_changed_at) },
                    { l: "Token Version", v: String(userDetail.token_version) },
                    { l: "Email Verified", v: userDetail.email_verified ? "Yes" : "No" },
                    { l: "Locked Until", v: userDetail.locked_until || "Not locked" },
                  ].map((x) => (
                    <div key={x.l} className="flex items-center justify-between p-2 rounded bg-zinc-800/30">
                      <span className="text-xs text-zinc-500">{x.l}</span>
                      <span className="text-xs font-medium font-mono max-w-[180px] truncate">{x.v}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
