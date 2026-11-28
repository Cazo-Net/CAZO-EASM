"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CalendarClock, Plus, Trash2, Loader2, Check, X, Pencil, Send, Download, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Schedule {
  id: string;
  name: string;
  frequency: "weekly" | "monthly";
  weekday: number;
  day_of_month: number;
  hour: number;
  timezone: string;
  recipients: string[];
  include_pdf: boolean;
  enabled: boolean;
  description: string;
  next_run_at: string | null;
  last_run_at: string | null;
  last_status: string | null;
  last_error: string | null;
}

interface Form {
  name: string;
  frequency: "weekly" | "monthly";
  weekday: number;
  day_of_month: number;
  hour: number;
  timezone: string;
  recipients: string;
  include_pdf: boolean;
}

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const SELECT =
  "h-9 w-full rounded-md border border-input bg-background px-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring";

function token(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("access_token") || sessionStorage.getItem("access_token") || "";
}

async function api(path: string, init: RequestInit = {}) {
  const res = await fetch(`/api/v1/report-schedules${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token()}`, ...(init.headers || {}) },
  });
  let data: any = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  return { ok: res.ok, status: res.status, data };
}

function errorText(data: any, fallback: string): string {
  return typeof data?.detail === "string" ? data.detail : fallback;
}

function browserZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

function zoneList(current: string): string[] {
  let zones: string[] = [];
  try {
    zones = (Intl as any).supportedValuesOf ? (Intl as any).supportedValuesOf("timeZone") : [];
  } catch {
    zones = [];
  }
  const set = new Set<string>(["UTC", ...zones]);
  if (current) set.add(current);
  return Array.from(set).sort();
}

function statusOf(s: Schedule, emailReady: boolean): { label: string; dot: string } {
  if (!s.enabled) return { label: "Paused", dot: "bg-muted-foreground/40" };
  if (!emailReady || s.last_status === "not_configured") return { label: "Waiting for email setup", dot: "bg-yellow-400" };
  if (s.last_status === "failed") return { label: "Last send failed", dot: "bg-red-400" };
  if (s.last_status === "partial") return { label: "Some emails failed", dot: "bg-yellow-400" };
  if (s.last_status === "sent") return { label: "Working", dot: "bg-green-400" };
  return { label: "Scheduled", dot: "bg-green-400" };
}

export function ScheduledReportsPanel() {
  const [items, setItems] = useState<Schedule[]>([]);
  const [emailReady, setEmailReady] = useState(true);
  const [yourEmail, setYourEmail] = useState("");
  const [limits, setLimits] = useState({ schedules: 10, recipients: 20 });
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);

  const [form, setForm] = useState<Form | null>(null);
  const [editing, setEditing] = useState<Schedule | null>(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<{ id: string; ok: boolean; text: string } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const zones = useMemo(() => zoneList(form?.timezone || ""), [form?.timezone]);

  const load = useCallback(async () => {
    const res = await api("");
    if (res.status === 403) setPageError("Only owners and administrators can manage scheduled reports.");
    else if (res.status === 404) setPageError("Create or join an organization to schedule reports.");
    else if (!res.ok) setPageError("Scheduled reports could not be loaded. Please try again.");
    else {
      setPageError(null);
      setItems(res.data.schedules || []);
      setEmailReady(!!res.data.email_configured);
      setYourEmail(res.data.your_email || "");
      setLimits({ schedules: res.data.max_schedules || 10, recipients: res.data.max_recipients || 20 });
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load().catch(() => {
      setPageError("Scheduled reports could not be loaded. Please try again.");
      setLoading(false);
    });
  }, [load]);

  const openAdd = () => {
    setEditing(null);
    setFormError(null);
    setForm({
      name: "", frequency: "weekly", weekday: 0, day_of_month: 1, hour: 8, timezone: browserZone(),
      recipients: yourEmail, include_pdf: true,
    });
  };

  const openEdit = (s: Schedule) => {
    setEditing(s);
    setFormError(null);
    setForm({
      name: s.name, frequency: s.frequency, weekday: s.weekday, day_of_month: s.day_of_month, hour: s.hour,
      timezone: s.timezone, recipients: s.recipients.join("\n"), include_pdf: s.include_pdf,
    });
  };

  const closeForm = () => {
    setForm(null);
    setEditing(null);
    setFormError(null);
  };

  const save = async () => {
    if (!form) return;
    const recipients = form.recipients.split(/[\s,;]+/).map((r) => r.trim()).filter(Boolean);
    if (recipients.length === 0) {
      setFormError("Add at least one email address.");
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      const body = JSON.stringify({ ...form, recipients });
      const res = editing ? await api(`/${editing.id}`, { method: "PUT", body }) : await api("", { method: "POST", body });
      if (!res.ok) {
        setFormError(errorText(res.data, "Could not save. Please check the details and try again."));
        return;
      }
      closeForm();
      await load();
    } catch {
      setFormError("Could not save. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  const sendNow = async (s: Schedule) => {
    setBusy(s.id);
    setNote(null);
    try {
      const res = await api(`/${s.id}/send-now`, { method: "POST" });
      const ok = res.ok && res.data?.status === "sent";
      setNote({
        id: s.id,
        ok,
        text: ok ? `Sent to ${res.data.sent_to}. Check your inbox.` : res.data?.error || errorText(res.data, "The email could not be sent."),
      });
    } catch {
      setNote({ id: s.id, ok: false, text: "The email could not be sent." });
    } finally {
      setBusy(null);
    }
  };

  const download = async (s: Schedule) => {
    setBusy(s.id);
    setNote(null);
    try {
      const res = await fetch(`/api/v1/report-schedules/${s.id}/preview.pdf`, { headers: { Authorization: `Bearer ${token()}` } });
      if (!res.ok) throw new Error("failed");
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = "cazo-security-report-preview.pdf";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setNote({ id: s.id, ok: false, text: "The PDF could not be created." });
    } finally {
      setBusy(null);
    }
  };

  const toggle = async (s: Schedule) => {
    setBusy(s.id);
    try {
      await api(`/${s.id}`, { method: "PUT", body: JSON.stringify({ enabled: !s.enabled }) });
      await load();
    } finally {
      setBusy(null);
    }
  };

  const remove = async (s: Schedule) => {
    setBusy(s.id);
    try {
      await api(`/${s.id}`, { method: "DELETE" });
      setConfirmDelete(null);
      await load();
    } finally {
      setBusy(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <CalendarClock className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="text-base font-semibold text-foreground">Scheduled reports</h2>
          <p className="text-xs text-muted-foreground">
            Email a security summary to your team or your client every week or month, with an optional PDF.
          </p>
        </div>
        {!pageError && !form && items.length < limits.schedules && (
          <Button size="sm" className="h-8 shrink-0 text-xs" onClick={openAdd}>
            <Plus className="mr-1 h-3.5 w-3.5" />
            New report
          </Button>
        )}
      </div>

      {pageError ? (
        <div role="alert" className="rounded-lg border border-border bg-muted/20 px-3 py-2 text-sm text-muted-foreground">
          {pageError}
        </div>
      ) : (
        <>
          {!emailReady && (
            <div role="status" className="mb-4 flex items-start gap-2 rounded-lg border border-yellow-500/40 bg-yellow-500/5 px-3 py-2 text-xs text-foreground">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-yellow-500" />
              Email sending is not set up on this platform yet, so reports will not go out. You can still create schedules
              and download the PDF.
            </div>
          )}

          {form && (
            <div className="mb-6 rounded-lg border border-border bg-muted/20 p-4">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-sm font-medium">{editing ? `Edit ${editing.name}` : "New scheduled report"}</h3>
                <button type="button" onClick={closeForm} aria-label="Close" className="text-muted-foreground hover:text-foreground">
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="space-y-3">
                <div>
                  <label htmlFor="rep-name" className="mb-1 block text-xs text-muted-foreground">Name (optional)</label>
                  <Input id="rep-name" value={form.name} maxLength={80} className="h-9 text-sm"
                    placeholder="e.g. Weekly report for the board"
                    onChange={(e) => setForm({ ...form, name: e.target.value })} />
                </div>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  <div>
                    <label htmlFor="rep-freq" className="mb-1 block text-xs text-muted-foreground">How often</label>
                    <select id="rep-freq" className={SELECT} value={form.frequency}
                      onChange={(e) => setForm({ ...form, frequency: e.target.value as Form["frequency"] })}>
                      <option value="weekly">Every week</option>
                      <option value="monthly">Every month</option>
                    </select>
                  </div>
                  {form.frequency === "weekly" ? (
                    <div>
                      <label htmlFor="rep-day" className="mb-1 block text-xs text-muted-foreground">Day</label>
                      <select id="rep-day" className={SELECT} value={form.weekday}
                        onChange={(e) => setForm({ ...form, weekday: Number(e.target.value) })}>
                        {WEEKDAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
                      </select>
                    </div>
                  ) : (
                    <div>
                      <label htmlFor="rep-dom" className="mb-1 block text-xs text-muted-foreground">Day of the month</label>
                      <select id="rep-dom" className={SELECT} value={form.day_of_month}
                        onChange={(e) => setForm({ ...form, day_of_month: Number(e.target.value) })}>
                        {Array.from({ length: 28 }, (_, i) => i + 1).map((d) => <option key={d} value={d}>{d}</option>)}
                      </select>
                    </div>
                  )}
                  <div>
                    <label htmlFor="rep-hour" className="mb-1 block text-xs text-muted-foreground">Time</label>
                    <select id="rep-hour" className={SELECT} value={form.hour}
                      onChange={(e) => setForm({ ...form, hour: Number(e.target.value) })}>
                      {Array.from({ length: 24 }, (_, h) => h).map((h) => (
                        <option key={h} value={h}>{String(h).padStart(2, "0")}:00</option>
                      ))}
                    </select>
                  </div>
                </div>
                <div>
                  <label htmlFor="rep-tz" className="mb-1 block text-xs text-muted-foreground">Time zone</label>
                  <select id="rep-tz" className={SELECT} value={form.timezone}
                    onChange={(e) => setForm({ ...form, timezone: e.target.value })}>
                    {zones.map((z) => <option key={z} value={z}>{z.replace(/_/g, " ")}</option>)}
                  </select>
                </div>
                <div>
                  <label htmlFor="rep-to" className="mb-1 block text-xs text-muted-foreground">
                    Send to (one email address per line, up to {limits.recipients})
                  </label>
                  <textarea id="rep-to" rows={3} value={form.recipients} spellCheck={false}
                    onChange={(e) => setForm({ ...form, recipients: e.target.value })}
                    placeholder={"ciso@example.com\nit-manager@example.com"}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring" />
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    Recipients do not need an account. The report shows finding names and hosts, so add only people who
                    should see them.
                  </p>
                </div>
                <label className="flex cursor-pointer items-center gap-2 text-xs text-foreground">
                  <input type="checkbox" className="h-3.5 w-3.5 accent-[hsl(var(--primary))]" checked={form.include_pdf}
                    onChange={(e) => setForm({ ...form, include_pdf: e.target.checked })} />
                  Attach the report as a PDF
                </label>
                {formError && (
                  <div role="alert" className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-foreground">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-destructive" />
                    {formError}
                  </div>
                )}
                <div className="flex justify-end gap-2 pt-1">
                  <Button size="sm" variant="outline" className="h-8 text-xs" onClick={closeForm} disabled={saving}>Cancel</Button>
                  <Button size="sm" className="h-8 text-xs" onClick={save} disabled={saving}>
                    {saving && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                    {editing ? "Save changes" : "Create report"}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {items.length === 0 ? (
            !form && (
              <p className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-sm text-muted-foreground">
                No scheduled reports yet. Create one to keep your team or client updated without logging in.
              </p>
            )
          ) : (
            <ul className="space-y-3">
              {items.map((s) => {
                const st = statusOf(s, emailReady);
                return (
                  <li key={s.id} className="rounded-lg border border-border p-3">
                    <div className="flex flex-wrap items-start gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-medium text-foreground">{s.name}</span>
                          <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                            <span className={`h-1.5 w-1.5 rounded-full ${st.dot}`} />
                            {st.label}
                          </span>
                        </div>
                        <div className="mt-0.5 text-[11px] text-muted-foreground">
                          Sends {s.description}
                          {s.include_pdf && " · PDF attached"}
                        </div>
                        <div className="mt-0.5 break-all text-[11px] text-muted-foreground">To {s.recipients.join(", ")}</div>
                        <div className="mt-1 text-[11px] text-muted-foreground">
                          {s.next_run_at && `Next: ${new Date(s.next_run_at).toLocaleString()}`}
                          {s.next_run_at && s.last_run_at && " · "}
                          {s.last_run_at && `Last: ${new Date(s.last_run_at).toLocaleString()}`}
                        </div>
                        {s.last_error && note?.id !== s.id && s.enabled && (
                          <div className="mt-1.5 flex items-start gap-1.5 text-[11px] text-yellow-500">
                            <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                            <span>{s.last_error}</span>
                          </div>
                        )}
                        {note?.id === s.id && (
                          <div role="status" className={`mt-1.5 flex items-start gap-1.5 text-[11px] ${note.ok ? "text-green-500" : "text-destructive"}`}>
                            {note.ok ? <Check className="mt-0.5 h-3 w-3 shrink-0" /> : <X className="mt-0.5 h-3 w-3 shrink-0" />}
                            <span>{note.text}</span>
                          </div>
                        )}
                      </div>
                      <div className="flex shrink-0 flex-wrap items-center gap-1.5">
                        <Button size="sm" variant="outline" className="h-7 px-2 text-[11px]" disabled={busy === s.id || !emailReady}
                          title={emailReady ? `Sends one copy to ${yourEmail}` : "Email is not set up yet"} onClick={() => sendNow(s)}>
                          {busy === s.id ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Send className="mr-1 h-3 w-3" />}
                          Send me a copy
                        </Button>
                        <Button size="sm" variant="outline" className="h-7 px-2 text-[11px]" disabled={busy === s.id} onClick={() => download(s)}>
                          <Download className="mr-1 h-3 w-3" />
                          PDF
                        </Button>
                        <Button size="sm" variant="outline" className="h-7 px-2 text-[11px]" disabled={busy === s.id} onClick={() => toggle(s)}>
                          {s.enabled ? "Pause" : "Resume"}
                        </Button>
                        <Button size="sm" variant="outline" className="h-7 px-2" aria-label={`Edit ${s.name}`} onClick={() => openEdit(s)}>
                          <Pencil className="h-3 w-3" />
                        </Button>
                        {confirmDelete === s.id ? (
                          <>
                            <Button size="sm" variant="destructive" className="h-7 px-2 text-[11px]" disabled={busy === s.id} onClick={() => remove(s)}>
                              Delete
                            </Button>
                            <Button size="sm" variant="outline" className="h-7 px-2 text-[11px]" onClick={() => setConfirmDelete(null)}>
                              Keep
                            </Button>
                          </>
                        ) : (
                          <Button size="sm" variant="outline" className="h-7 px-2" aria-label={`Delete ${s.name}`} onClick={() => setConfirmDelete(s.id)}>
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        )}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
