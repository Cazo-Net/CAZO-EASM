"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Plug,
  Plus,
  Trash2,
  Loader2,
  Check,
  X,
  Pencil,
  Send,
  MessageSquare,
  Users,
  Ticket,
  Server,
  AlertTriangle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

interface FieldSpec {
  key: string;
  label: string;
  secret?: boolean;
  required?: boolean;
  placeholder?: string;
  help?: string;
}

interface KindSpec {
  kind: string;
  label: string;
  description: string;
  fields: FieldSpec[];
  default_events: string[];
}

interface EventSpec {
  type: string;
  label: string;
}

interface Integration {
  id: string;
  kind: string;
  name: string;
  enabled: boolean;
  settings: Record<string, string>;
  has_secret: boolean;
  credentials_readable: boolean;
  destination: string;
  event_types: string[];
  failure_count: number;
  last_success_at: string | null;
  last_failure_at: string | null;
  last_error: string | null;
}

const ICONS: Record<string, any> = { slack: MessageSquare, teams: Users, jira: Ticket, splunk: Server };

function token(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("access_token") || sessionStorage.getItem("access_token") || "";
}

async function api(path: string, init: RequestInit = {}) {
  const res = await fetch(`/api/v1/integrations${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token()}`,
      ...(init.headers || {}),
    },
  });
  let data: any = null;
  if (res.status !== 204) {
    try {
      data = await res.json();
    } catch {
      data = null;
    }
  }
  return { ok: res.ok, status: res.status, data };
}

function errorText(data: any, fallback: string): string {
  return typeof data?.detail === "string" ? data.detail : fallback;
}

function statusOf(i: Integration): { label: string; dot: string } {
  if (!i.credentials_readable) return { label: "Needs credentials", dot: "bg-red-400" };
  if (!i.enabled) return { label: "Off", dot: "bg-muted-foreground/40" };
  if (i.failure_count > 0) return { label: "Failing", dot: "bg-yellow-400" };
  if (i.last_success_at) return { label: "Working", dot: "bg-green-400" };
  return { label: "Not used yet", dot: "bg-muted-foreground/40" };
}

export function IntegrationsPanel() {
  const [kinds, setKinds] = useState<KindSpec[]>([]);
  const [events, setEvents] = useState<EventSpec[]>([]);
  const [items, setItems] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);

  // Form: adding (kind set, editing null) or editing an existing integration.
  const [formKind, setFormKind] = useState<string | null>(null);
  const [editing, setEditing] = useState<Integration | null>(null);
  const [name, setName] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [busy, setBusy] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ id: string; ok: boolean; text: string } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [cat, list] = await Promise.all([api("/catalog"), api("")]);
    if (cat.status === 403 || list.status === 403) {
      setPageError("Only owners and administrators can manage integrations.");
    } else if (list.status === 404) {
      setPageError("Create or join an organization to set up integrations.");
    } else if (!cat.ok || !list.ok) {
      setPageError("Integrations could not be loaded. Please try again.");
    } else {
      setPageError(null);
      setKinds(cat.data.kinds || []);
      setEvents(cat.data.events || []);
      setItems(list.data || []);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load().catch(() => {
      setPageError("Integrations could not be loaded. Please try again.");
      setLoading(false);
    });
  }, [load]);

  const spec = kinds.find((k) => k.kind === formKind) || null;

  const openAdd = (kind: KindSpec) => {
    setEditing(null);
    setFormKind(kind.kind);
    setName("");
    setValues({});
    setSelected(kind.default_events);
    setFormError(null);
  };

  const openEdit = (i: Integration) => {
    setEditing(i);
    setFormKind(i.kind);
    setName(i.name);
    setValues({ ...i.settings });
    setSelected(i.event_types);
    setFormError(null);
  };

  const closeForm = () => {
    setFormKind(null);
    setEditing(null);
    setFormError(null);
  };

  const save = async () => {
    if (!spec) return;
    if (selected.length === 0) {
      setFormError("Choose at least one event to send.");
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      const body = { name, settings: values, event_types: selected };
      const res = editing
        ? await api(`/${editing.id}`, { method: "PUT", body: JSON.stringify(body) })
        : await api("", { method: "POST", body: JSON.stringify({ ...body, kind: spec.kind }) });
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

  const test = async (i: Integration) => {
    setBusy(i.id);
    setTestResult(null);
    try {
      const res = await api(`/${i.id}/test`, { method: "POST" });
      const ok = res.ok && res.data?.success;
      setTestResult({
        id: i.id,
        ok,
        text: ok
          ? i.kind === "jira"
            ? "Connected. The account can reach the project (no issue was created)."
            : "Test sent. Check the destination."
          : res.data?.error || errorText(res.data, "The test failed."),
      });
      await load();
    } catch {
      setTestResult({ id: i.id, ok: false, text: "The test failed." });
    } finally {
      setBusy(null);
    }
  };

  const toggle = async (i: Integration) => {
    setBusy(i.id);
    try {
      await api(`/${i.id}`, { method: "PUT", body: JSON.stringify({ enabled: !i.enabled }) });
      await load();
    } finally {
      setBusy(null);
    }
  };

  const remove = async (i: Integration) => {
    setBusy(i.id);
    try {
      await api(`/${i.id}`, { method: "DELETE" });
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
          <Plug className="h-4 w-4" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-foreground">Integrations</h2>
          <p className="text-xs text-muted-foreground">
            Send new findings and alerts to the tools your team already uses. Credentials are stored encrypted and are
            never shown again.
          </p>
        </div>
      </div>

      {pageError ? (
        <div role="alert" className="rounded-lg border border-border bg-muted/20 px-3 py-2 text-sm text-muted-foreground">
          {pageError}
        </div>
      ) : (
        <>
          {/* Add */}
          {!formKind && (
            <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
              {kinds.map((k) => {
                const Icon = ICONS[k.kind] || Plug;
                return (
                  <button
                    key={k.kind}
                    type="button"
                    onClick={() => openAdd(k)}
                    className="flex items-start gap-3 rounded-lg border border-border p-3 text-left transition-colors hover:border-primary/40 hover:bg-muted/20"
                  >
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted/40 text-foreground">
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium text-foreground">{k.label}</div>
                      <div className="text-xs text-muted-foreground">{k.description}</div>
                    </div>
                    <Plus className="h-4 w-4 shrink-0 text-muted-foreground" />
                  </button>
                );
              })}
            </div>
          )}

          {/* Form */}
          {spec && (
            <div className="mb-6 rounded-lg border border-border bg-muted/20 p-4">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-sm font-medium">
                  {editing ? `Edit ${editing.name}` : `Connect ${spec.label}`}
                </h3>
                <button type="button" onClick={closeForm} aria-label="Close" className="text-muted-foreground hover:text-foreground">
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="space-y-3">
                <div>
                  <label htmlFor="int-name" className="mb-1 block text-xs text-muted-foreground">Name (optional)</label>
                  <Input id="int-name" value={name} maxLength={80} onChange={(e) => setName(e.target.value)}
                    placeholder={`e.g. ${spec.label} for the security team`} className="h-9 text-sm" />
                </div>
                {spec.fields.map((f) => (
                  <div key={f.key}>
                    <label htmlFor={`int-${f.key}`} className="mb-1 block text-xs text-muted-foreground">
                      {f.label}
                      {!f.required && " (optional)"}
                    </label>
                    <Input
                      id={`int-${f.key}`}
                      type={f.secret ? "password" : "text"}
                      autoComplete={f.secret ? "new-password" : "off"}
                      value={values[f.key] || ""}
                      onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
                      placeholder={f.secret && editing ? "Leave blank to keep the current one" : f.placeholder}
                      className="h-9 text-sm"
                    />
                    {f.help && <p className="mt-1 text-[11px] text-muted-foreground">{f.help}</p>}
                  </div>
                ))}
                <fieldset>
                  <legend className="mb-1.5 text-xs text-muted-foreground">Send these events</legend>
                  <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                    {events.map((ev) => (
                      <label key={ev.type} className="flex cursor-pointer items-center gap-2 text-xs text-foreground">
                        <input
                          type="checkbox"
                          className="h-3.5 w-3.5 accent-[hsl(var(--primary))]"
                          checked={selected.includes(ev.type)}
                          onChange={() =>
                            setSelected((s) => (s.includes(ev.type) ? s.filter((x) => x !== ev.type) : [...s, ev.type]))
                          }
                        />
                        {ev.label}
                      </label>
                    ))}
                  </div>
                </fieldset>
                {formError && (
                  <div role="alert" className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-foreground">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-destructive" />
                    {formError}
                  </div>
                )}
                <div className="flex justify-end gap-2 pt-1">
                  <Button size="sm" variant="outline" className="h-8 text-xs" onClick={closeForm} disabled={saving}>
                    Cancel
                  </Button>
                  <Button size="sm" className="h-8 text-xs" onClick={save} disabled={saving}>
                    {saving && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                    {editing ? "Save changes" : "Connect"}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* List */}
          {items.length === 0 ? (
            !formKind && (
              <p className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-sm text-muted-foreground">
                Nothing connected yet. Pick a tool above to start.
              </p>
            )
          ) : (
            <ul className="space-y-3">
              {items.map((i) => {
                const Icon = ICONS[i.kind] || Plug;
                const st = statusOf(i);
                const kindLabel = kinds.find((k) => k.kind === i.kind)?.label || i.kind;
                return (
                  <li key={i.id} className="rounded-lg border border-border p-3">
                    <div className="flex flex-wrap items-start gap-3">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted/40 text-foreground">
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-medium text-foreground">{i.name}</span>
                          {i.name !== kindLabel && <Badge variant="outline" className="text-[10px]">{kindLabel}</Badge>}
                          <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                            <span className={`h-1.5 w-1.5 rounded-full ${st.dot}`} />
                            {st.label}
                          </span>
                        </div>
                        <div className="mt-0.5 break-all font-mono text-[11px] text-muted-foreground">{i.destination}</div>
                        <div className="mt-1 text-[11px] text-muted-foreground">
                          {i.event_types.length} {i.event_types.length === 1 ? "event" : "events"}
                          {i.last_success_at && ` · last delivered ${new Date(i.last_success_at).toLocaleString()}`}
                        </div>
                        {i.last_error && testResult?.id !== i.id && (
                          <div className="mt-1.5 flex items-start gap-1.5 text-[11px] text-yellow-500">
                            <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                            <span>{i.last_error}</span>
                          </div>
                        )}
                        {testResult?.id === i.id && (
                          <div role="status" className={`mt-1.5 flex items-start gap-1.5 text-[11px] ${testResult.ok ? "text-green-500" : "text-destructive"}`}>
                            {testResult.ok ? <Check className="mt-0.5 h-3 w-3 shrink-0" /> : <X className="mt-0.5 h-3 w-3 shrink-0" />}
                            <span>{testResult.text}</span>
                          </div>
                        )}
                      </div>
                      <div className="flex shrink-0 items-center gap-1.5">
                        <Button size="sm" variant="outline" className="h-7 px-2 text-[11px]" disabled={busy === i.id || !i.credentials_readable}
                          onClick={() => test(i)}>
                          {busy === i.id ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <Send className="mr-1 h-3 w-3" />}
                          Test
                        </Button>
                        <Button size="sm" variant="outline" className="h-7 px-2 text-[11px]" disabled={busy === i.id} onClick={() => toggle(i)}>
                          {i.enabled ? "Turn off" : "Turn on"}
                        </Button>
                        <Button size="sm" variant="outline" className="h-7 px-2" aria-label={`Edit ${i.name}`} onClick={() => openEdit(i)}>
                          <Pencil className="h-3 w-3" />
                        </Button>
                        {confirmDelete === i.id ? (
                          <>
                            <Button size="sm" variant="destructive" className="h-7 px-2 text-[11px]" disabled={busy === i.id} onClick={() => remove(i)}>
                              Remove
                            </Button>
                            <Button size="sm" variant="outline" className="h-7 px-2 text-[11px]" onClick={() => setConfirmDelete(null)}>
                              Keep
                            </Button>
                          </>
                        ) : (
                          <Button size="sm" variant="outline" className="h-7 px-2" aria-label={`Remove ${i.name}`} onClick={() => setConfirmDelete(i.id)}>
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

          <p className="mt-6 text-[11px] text-muted-foreground">
            Using another SIEM or your own system? Add a signed webhook under Webhooks and point it at your collector.
          </p>
        </>
      )}
    </div>
  );
}
