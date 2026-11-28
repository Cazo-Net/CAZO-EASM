"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle, ArrowLeft, Building, CheckCircle, Clock, Globe, Loader2, Monitor,
  RefreshCw, Smartphone, Tablet, XCircle,
} from "lucide-react";
import api, { getErrorMessage } from "@/lib/api";

export type DiagnosticsTarget = { kind: "user" | "session"; id: string };

interface SessionInfo {
  id: string;
  is_active: boolean;
  ip_address: string | null;
  location: string | null;
  user_agent: string | null;
  browser: string;
  os: string;
  device_type: string;
  created_at: string | null;
  last_activity: string | null;
  expires_at: string | null;
}

interface AuthEvent {
  id: string;
  event_type: string;
  success: boolean;
  ip_address: string | null;
  browser?: string;
  os?: string;
  detail: Record<string, unknown>;
  created_at: string | null;
}

interface ErrorEvent {
  id: string;
  category: string;
  severity: string;
  message: string;
  path: string | null;
  method: string | null;
  status_code: number | null;
  request_id: string | null;
  browser: string | null;
  created_at: string | null;
}

interface ActivityEvent {
  id: string;
  action: string;
  status: string | null;
  target_type: string | null;
  ip_address: string | null;
  created_at: string | null;
}

function fmt(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString([], { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function ago(iso: string | null | undefined): string {
  if (!iso) return "never";
  const ms = Date.now() - new Date(iso).getTime();
  if (Number.isNaN(ms)) return "—";
  const min = Math.floor(ms / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min} min ago`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h} h ago`;
  return `${Math.floor(h / 24)} d ago`;
}

function DeviceIcon({ type }: { type: string }) {
  const cls = "h-4 w-4 text-zinc-400";
  if (type === "mobile") return <Smartphone className={cls} />;
  if (type === "tablet") return <Tablet className={cls} />;
  return <Monitor className={cls} />;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="text-[11px] uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="text-sm break-words">{children}</div>
    </div>
  );
}

function Section({ title, count, children }: { title: string; count?: number; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-zinc-800 overflow-hidden">
      <div className="px-4 py-2.5 bg-zinc-800/50 text-sm font-medium flex items-center gap-2">
        {title}
        {count !== undefined && <span className="text-xs text-zinc-500">{count}</span>}
      </div>
      {children}
    </section>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div className="px-4 py-6 text-center text-sm text-zinc-500">{children}</div>;
}

function ErrorsTable({ rows }: { rows: ErrorEvent[] }) {
  if (rows.length === 0) return <Empty>No errors recorded for this client</Empty>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <tbody>
          {rows.map((e) => (
            <tr key={e.id} className="border-t border-zinc-800 align-top">
              <td className="px-4 py-2 text-xs text-zinc-500 whitespace-nowrap">{fmt(e.created_at)}</td>
              <td className="px-2 py-2">
                <span className={`px-1.5 py-0.5 rounded text-xs ${e.severity === "warning" ? "bg-amber-500/20 text-amber-400" : "bg-red-500/20 text-red-400"}`}>
                  {e.status_code || (e.category === "unexpected" ? "browser" : e.severity)}
                </span>
              </td>
              <td className="px-2 py-2 min-w-0">
                <div className="break-words">{e.message}</div>
                <div className="text-xs text-zinc-500 font-mono break-all">
                  {[e.path && !e.message.includes(e.path) ? e.path : null, e.browser, e.request_id ? `req ${e.request_id}` : null].filter(Boolean).join(" · ")}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AuthTable({ rows }: { rows: AuthEvent[] }) {
  if (rows.length === 0) return <Empty>No sign-in events</Empty>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <tbody>
          {rows.map((e) => (
            <tr key={e.id} className="border-t border-zinc-800">
              <td className="px-4 py-2 text-xs text-zinc-500 whitespace-nowrap">{fmt(e.created_at)}</td>
              <td className="px-2 py-2">
                <span className="inline-flex items-center gap-1.5">
                  {e.success ? <CheckCircle className="h-3.5 w-3.5 text-green-400" /> : <XCircle className="h-3.5 w-3.5 text-red-400" />}
                  {e.event_type.replace(/_/g, " ")}
                  {typeof e.detail?.method === "string" && <span className="text-xs text-zinc-500">({e.detail.method})</span>}
                </span>
              </td>
              <td className="px-2 py-2 font-mono text-xs">{e.ip_address || "—"}</td>
              <td className="px-4 py-2 text-xs text-zinc-500">{[e.browser, e.os].filter(Boolean).join(" · ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Technical details staff need to investigate a customer's problem. Read-only. */
export function ClientDiagnostics({ target, onClose }: { target: DiagnosticsTarget; onClose: () => void }) {
  const [current, setCurrent] = useState<DiagnosticsTarget>(target);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => setCurrent(target), [target]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get(`/diagnostics/${current.kind === "user" ? "users" : "sessions"}/${current.id}`);
      setData(res.data);
      setError("");
    } catch (e) {
      setError(getErrorMessage(e));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [current]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const user = data?.user;
  const org = data?.organization;
  const sub = org?.subscription;
  const isSession = current.kind === "session";

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-zinc-900 border-l border-zinc-700 w-full max-w-4xl h-full overflow-y-auto p-6 space-y-4" onClick={(e) => e.stopPropagation()}
        role="dialog" aria-label="Client diagnostics">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            {isSession && user && (
              <button onClick={() => setCurrent({ kind: "user", id: user.id })}
                className="mb-1 flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300">
                <ArrowLeft className="h-3 w-3" /> All diagnostics for this client
              </button>
            )}
            <h2 className="text-lg font-bold">{isSession ? "Session diagnostics" : "Client diagnostics"}</h2>
            <p className="text-xs text-zinc-500 truncate">
              {user ? `${user.full_name || "No name"} · ${user.email}` : "Loading…"}
            </p>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <button onClick={load} className="p-2 rounded-lg hover:bg-zinc-800" title="Refresh">
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            </button>
            <button onClick={onClose} className="p-2 rounded-lg hover:bg-zinc-800" title="Close"><XCircle className="h-5 w-5" /></button>
          </div>
        </div>

        {error && <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">{error}</div>}

        {data && !isSession && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="rounded-xl border border-zinc-800 p-3">
                <div className="text-[11px] uppercase tracking-wide text-zinc-500">Browser</div>
                <div className="mt-1 flex items-center gap-2 text-sm font-medium">
                  <DeviceIcon type={data.summary.device_type || ""} />{data.summary.browser || "—"}
                </div>
                <div className="text-xs text-zinc-500">{[data.summary.os, data.summary.device_type].filter(Boolean).join(" · ") || "No sessions yet"}</div>
              </div>
              <div className="rounded-xl border border-zinc-800 p-3">
                <div className="text-[11px] uppercase tracking-wide text-zinc-500">Last IP</div>
                <div className="mt-1 flex items-center gap-2 text-sm font-medium font-mono"><Globe className="h-4 w-4 text-zinc-400" />{data.summary.ip_address || "—"}</div>
                <div className="text-xs text-zinc-500">{data.summary.location ? `${data.summary.location} (approx.)` : "Location unknown"}</div>
              </div>
              <div className="rounded-xl border border-zinc-800 p-3">
                <div className="text-[11px] uppercase tracking-wide text-zinc-500">Last seen</div>
                <div className="mt-1 flex items-center gap-2 text-sm font-medium"><Clock className="h-4 w-4 text-zinc-400" />{ago(data.summary.last_seen)}</div>
                <div className="text-xs text-zinc-500">{data.summary.active_sessions} active session{data.summary.active_sessions === 1 ? "" : "s"}</div>
              </div>
              <div className="rounded-xl border border-zinc-800 p-3">
                <div className="text-[11px] uppercase tracking-wide text-zinc-500">Last 7 days</div>
                <div className={`mt-1 flex items-center gap-2 text-sm font-medium ${data.summary.errors_7d > 0 ? "text-red-400" : ""}`}>
                  <AlertTriangle className="h-4 w-4" />{data.summary.errors_7d} error{data.summary.errors_7d === 1 ? "" : "s"}
                </div>
                <div className="text-xs text-zinc-500">{data.summary.failed_logins_7d} failed sign-in{data.summary.failed_logins_7d === 1 ? "" : "s"}</div>
              </div>
            </div>

            <Section title="Account">
              <div className="p-4 grid grid-cols-2 md:grid-cols-4 gap-4">
                <Field label="Status">
                  <span className={user.is_active ? "text-green-400" : "text-red-400"}>{user.is_active ? "Active" : "Disabled"}</span>
                  {user.locked_until && <span className="ml-2 px-1.5 py-0.5 rounded text-xs bg-red-500/20 text-red-400">Locked until {fmt(user.locked_until)}</span>}
                </Field>
                <Field label="Role">{user.role || "—"}</Field>
                <Field label="Sign-in">{user.sign_in_method === "google" ? "Google" : "Password"}{user.totp_enabled ? " + 2FA" : ""}</Field>
                <Field label="Email verified">{user.email_verified ? "Yes" : "No"}</Field>
                <Field label="Created">{fmt(user.created_at)}</Field>
                <Field label="Last login">{fmt(user.last_login)}</Field>
                <Field label="Password changed">{fmt(user.password_changed_at)}</Field>
                <Field label="Failed logins (current)">{user.failed_login_attempts}</Field>
                <Field label="Organization">
                  <span className="inline-flex items-center gap-1.5"><Building className="h-3.5 w-3.5 text-zinc-400" />{org?.name || "None"}</span>
                </Field>
                <Field label="Plan">{sub?.plan || org?.plan || "—"}</Field>
                <Field label="Subscription">
                  {sub ? <span className={sub.status === "active" || sub.status === "trialing" ? "" : "text-amber-400"}>{sub.status}{sub.cancel_at_period_end ? " (cancels at period end)" : ""}</span> : "—"}
                </Field>
                <Field label="Renews / ends">{fmt(sub?.current_period_end)}</Field>
                {sub?.last_payment_error && (
                  <div className="col-span-2 md:col-span-4"><Field label="Last payment error"><span className="text-amber-400">{sub.last_payment_error}</span></Field></div>
                )}
              </div>
            </Section>

            <Section title="Recent errors" count={data.errors.length}><ErrorsTable rows={data.errors} /></Section>

            <Section title="Sessions" count={data.sessions.length}>
              {data.sessions.length === 0 ? <Empty>This client has never signed in</Empty> : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-xs text-zinc-500">
                      <tr>
                        <th className="text-left px-4 py-2 font-medium">Browser / OS</th>
                        <th className="text-left px-2 py-2 font-medium">IP</th>
                        <th className="text-left px-2 py-2 font-medium">Location</th>
                        <th className="text-left px-2 py-2 font-medium">Started</th>
                        <th className="text-left px-2 py-2 font-medium">Last activity</th>
                        <th className="text-left px-4 py-2 font-medium">State</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.sessions.map((s: SessionInfo) => (
                        <tr key={s.id} className="border-t border-zinc-800 hover:bg-zinc-800/40 cursor-pointer"
                          onClick={() => setCurrent({ kind: "session", id: s.id })} title="Open session diagnostics">
                          <td className="px-4 py-2">
                            <div className="flex items-center gap-2"><DeviceIcon type={s.device_type} />{s.browser}</div>
                            <div className="text-xs text-zinc-500 pl-6">{s.os} · {s.device_type}</div>
                          </td>
                          <td className="px-2 py-2 font-mono text-xs">{s.ip_address || "—"}</td>
                          <td className="px-2 py-2 text-xs">{s.location || "—"}</td>
                          <td className="px-2 py-2 text-xs text-zinc-500 whitespace-nowrap">{fmt(s.created_at)}</td>
                          <td className="px-2 py-2 text-xs text-zinc-500 whitespace-nowrap">{ago(s.last_activity)}</td>
                          <td className="px-4 py-2 text-xs">
                            <span className={s.is_active ? "text-green-400" : "text-zinc-500"}>{s.is_active ? "Active" : "Ended"}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Section>

            <Section title="Sign-in history" count={data.auth_events.length}><AuthTable rows={data.auth_events} /></Section>

            <Section title="Recent activity (audit log)" count={data.activity.length}>
              {data.activity.length === 0 ? <Empty>No audited actions</Empty> : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <tbody>
                      {data.activity.map((a: ActivityEvent) => (
                        <tr key={a.id} className="border-t border-zinc-800">
                          <td className="px-4 py-2 text-xs text-zinc-500 whitespace-nowrap">{fmt(a.created_at)}</td>
                          <td className="px-2 py-2 font-mono text-xs">{a.action}</td>
                          <td className="px-2 py-2 text-xs text-zinc-500">{a.target_type || ""}</td>
                          <td className="px-2 py-2 text-xs">
                            <span className={a.status === "success" ? "text-green-400" : "text-amber-400"}>{a.status || ""}</span>
                          </td>
                          <td className="px-4 py-2 font-mono text-xs">{a.ip_address || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Section>
          </>
        )}

        {data && isSession && data.session && (
          <>
            <Section title="Device and network">
              <div className="p-4 grid grid-cols-2 md:grid-cols-4 gap-4">
                <Field label="Browser"><span className="inline-flex items-center gap-2"><DeviceIcon type={data.session.device_type} />{data.session.browser}</span></Field>
                <Field label="Operating system">{data.session.os}</Field>
                <Field label="Device type">{data.session.device_type}</Field>
                <Field label="State"><span className={data.session.is_active ? "text-green-400" : "text-zinc-400"}>{data.session.is_active ? "Active" : "Ended"}</span></Field>
                <Field label="IP address"><span className="font-mono">{data.session.ip_address || "—"}</span></Field>
                <Field label="Location (approx.)">{data.session.location || "Unknown"}</Field>
                <Field label="Started">{fmt(data.session.created_at)}</Field>
                <Field label="Last activity">{fmt(data.session.last_activity)}</Field>
                <Field label="Organization">{org?.name || "None"}</Field>
                <Field label="Plan">{sub?.plan || org?.plan || "—"}</Field>
                <div className="col-span-2">
                  <Field label="Session ID"><span className="font-mono text-xs">{data.session.id}</span></Field>
                </div>
                <div className="col-span-2 md:col-span-4">
                  <Field label="User agent"><span className="font-mono text-xs break-all">{data.session.user_agent || "—"}</span></Field>
                </div>
              </div>
            </Section>
            <Section title="Errors during this session" count={data.errors.length}><ErrorsTable rows={data.errors} /></Section>
            <Section title="Sign-in events during this session" count={data.auth_events.length}><AuthTable rows={data.auth_events} /></Section>
          </>
        )}

        {data && (
          <p className="text-xs text-zinc-500">
            Technical details recorded while the client uses CAZO-EASM, for support and troubleshooting.
            Opening this view is recorded in the platform log.
          </p>
        )}
      </div>
    </div>
  );
}
