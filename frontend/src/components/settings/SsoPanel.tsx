"use client";

import { useCallback, useEffect, useState } from "react";
import { KeyRound, Plus, Trash2, Loader2, Check, X, Copy, AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

interface Domain {
  id: string;
  domain: string;
  verified: boolean;
  dns_record: { type: string; name: string; value: string };
}

interface Config {
  issuer: string;
  client_id: string;
  has_secret: boolean;
  enabled: boolean;
  enforce: boolean;
  auto_provision: boolean;
  default_role: string;
  last_login_at: string | null;
  last_error: string | null;
}

interface State {
  config: Config | null;
  domains: Domain[];
  redirect_uri: string;
  roles: string[];
  max_domains: number;
}

const SELECT =
  "h-9 w-full rounded-md border border-input bg-background px-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring";
const ROLE_LABELS: Record<string, string> = { viewer: "Viewer (read only)", analyst: "Analyst", admin: "Administrator" };

function token(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("access_token") || sessionStorage.getItem("access_token") || "";
}

async function api(path: string, init: RequestInit = {}) {
  const res = await fetch(`/api/v1/sso${path}`, {
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

function CopyValue({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable: the value is visible and can be selected */
    }
  };
  return (
    <div className="flex items-center gap-2">
      <span className="w-12 shrink-0 text-[11px] text-muted-foreground">{label}</span>
      <code className="min-w-0 flex-1 break-all rounded bg-muted/40 px-2 py-1 font-mono text-[11px] text-foreground">{value}</code>
      <button type="button" onClick={copy} aria-label={`Copy ${label}`} className="shrink-0 text-muted-foreground hover:text-foreground">
        {copied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
    </div>
  );
}

export function SsoPanel() {
  const [state, setState] = useState<State | null>(null);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);

  const [issuer, setIssuer] = useState("");
  const [clientId, setClientId] = useState("");
  const [secret, setSecret] = useState("");
  const [enabled, setEnabled] = useState(false);
  const [enforce, setEnforce] = useState(false);
  const [autoProvision, setAutoProvision] = useState(true);
  const [role, setRole] = useState("viewer");
  const [saving, setSaving] = useState(false);
  const [formNote, setFormNote] = useState<{ ok: boolean; text: string } | null>(null);

  const [newDomain, setNewDomain] = useState("");
  const [domainError, setDomainError] = useState<string | null>(null);
  const [domainNote, setDomainNote] = useState<{ id: string; text: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [confirmRemove, setConfirmRemove] = useState(false);

  const apply = (data: State) => {
    setState(data);
    const c = data.config;
    setIssuer(c?.issuer || "");
    setClientId(c?.client_id || "");
    setSecret("");
    setEnabled(!!c?.enabled);
    setEnforce(!!c?.enforce);
    setAutoProvision(c ? c.auto_provision : true);
    setRole(c?.default_role || "viewer");
  };

  const load = useCallback(async (keepForm = false) => {
    const res = await api("");
    if (res.status === 403) setPageError("Only owners and administrators can manage single sign-on.");
    else if (res.status === 404) setPageError("Create or join an organization to set up single sign-on.");
    else if (!res.ok) setPageError("Single sign-on settings could not be loaded. Please try again.");
    else {
      setPageError(null);
      if (keepForm) setState(res.data);
      else apply(res.data);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load().catch(() => {
      setPageError("Single sign-on settings could not be loaded. Please try again.");
      setLoading(false);
    });
  }, [load]);

  const hasVerified = !!state?.domains.some((d) => d.verified);

  const save = async () => {
    setSaving(true);
    setFormNote(null);
    try {
      const res = await api("", {
        method: "PUT",
        body: JSON.stringify({
          issuer, client_id: clientId, client_secret: secret || null, enabled, enforce: enabled && enforce,
          auto_provision: autoProvision, default_role: role,
        }),
      });
      if (!res.ok) {
        setFormNote({ ok: false, text: errorText(res.data, "Could not save. Please check the details and try again.") });
        return;
      }
      apply(res.data);
      setFormNote({ ok: true, text: "Saved." });
    } catch {
      setFormNote({ ok: false, text: "Could not save. Please try again." });
    } finally {
      setSaving(false);
    }
  };

  const test = async () => {
    setSaving(true);
    setFormNote(null);
    try {
      const res = await api("/test", { method: "POST" });
      setFormNote(res.ok && res.data?.success
        ? { ok: true, text: "Your identity provider answered correctly." }
        : { ok: false, text: res.data?.error || errorText(res.data, "The check failed.") });
    } finally {
      setSaving(false);
    }
  };

  const removeAll = async () => {
    setSaving(true);
    try {
      await api("", { method: "DELETE" });
      setConfirmRemove(false);
      setFormNote(null);
      await load();
    } finally {
      setSaving(false);
    }
  };

  const addDomain = async () => {
    setDomainError(null);
    setBusy("add");
    try {
      const res = await api("/domains", { method: "POST", body: JSON.stringify({ domain: newDomain }) });
      if (!res.ok) {
        setDomainError(errorText(res.data, "Could not add the domain."));
        return;
      }
      setNewDomain("");
      await load(true);
    } finally {
      setBusy(null);
    }
  };

  const verify = async (d: Domain) => {
    setBusy(d.id);
    setDomainNote(null);
    try {
      const res = await api(`/domains/${d.id}/verify`, { method: "POST" });
      if (!res.ok) setDomainNote({ id: d.id, text: errorText(res.data, "The check failed.") });
      else if (res.data?.error) setDomainNote({ id: d.id, text: res.data.error });
      await load(true);
    } finally {
      setBusy(null);
    }
  };

  const removeDomain = async (d: Domain) => {
    setBusy(d.id);
    try {
      const res = await api(`/domains/${d.id}`, { method: "DELETE" });
      // Removing the last verified domain turns SSO off on the server: reload the form too.
      await load(!res.data?.sso_turned_off);
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
          <KeyRound className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold text-foreground">Single sign-on</h2>
            {state?.config && (
              <Badge variant="outline" className="text-[10px]">
                {state.config.enabled ? (state.config.enforce ? "On, required" : "On") : "Off"}
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            Let your team sign in with your company identity provider (Microsoft Entra ID, Okta, Google Workspace,
            Keycloak and others that support OpenID Connect).
          </p>
        </div>
      </div>

      {pageError || !state ? (
        <div role="alert" className="rounded-lg border border-border bg-muted/20 px-3 py-2 text-sm text-muted-foreground">
          {pageError || "Single sign-on settings could not be loaded."}
        </div>
      ) : (
        <div className="space-y-6">
          {/* Step 1 */}
          <section className="rounded-lg border border-border p-4">
            <h3 className="text-sm font-medium text-foreground">1. Prove you own your email domain</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              Only people with an email address on a verified domain can sign in with your provider. Add the DNS record
              shown, then choose Check.
            </p>
            <ul className="mt-3 space-y-3">
              {state.domains.map((d) => (
                <li key={d.id} className="rounded-md border border-border p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-foreground">{d.domain}</span>
                    <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                      <span className={`h-1.5 w-1.5 rounded-full ${d.verified ? "bg-green-400" : "bg-yellow-400"}`} />
                      {d.verified ? "Verified" : "Waiting for DNS record"}
                    </span>
                    <div className="ml-auto flex items-center gap-1.5">
                      {!d.verified && (
                        <Button size="sm" variant="outline" className="h-7 px-2 text-[11px]" disabled={busy === d.id} onClick={() => verify(d)}>
                          {busy === d.id ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : <RefreshCw className="mr-1 h-3 w-3" />}
                          Check
                        </Button>
                      )}
                      <Button size="sm" variant="outline" className="h-7 px-2" aria-label={`Remove ${d.domain}`} disabled={busy === d.id}
                        onClick={() => removeDomain(d)}>
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                  {!d.verified && (
                    <div className="mt-2 space-y-1.5">
                      <CopyValue label="Type" value={d.dns_record.type} />
                      <CopyValue label="Name" value={d.dns_record.name} />
                      <CopyValue label="Value" value={d.dns_record.value} />
                    </div>
                  )}
                  {domainNote?.id === d.id && (
                    <div role="status" className="mt-2 flex items-start gap-1.5 text-[11px] text-yellow-500">
                      <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                      <span>{domainNote.text}</span>
                    </div>
                  )}
                </li>
              ))}
            </ul>
            {state.domains.length < state.max_domains && (
              <div className="mt-3 flex gap-2">
                <Input value={newDomain} onChange={(e) => setNewDomain(e.target.value)} placeholder="example.com"
                  aria-label="Email domain" className="h-9 text-sm"
                  onKeyDown={(e) => e.key === "Enter" && newDomain.trim() && addDomain()} />
                <Button size="sm" className="h-9 shrink-0 text-xs" disabled={!newDomain.trim() || busy === "add"} onClick={addDomain}>
                  {busy === "add" ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <Plus className="mr-1 h-3.5 w-3.5" />}
                  Add domain
                </Button>
              </div>
            )}
            {domainError && <p role="alert" className="mt-2 text-xs text-destructive">{domainError}</p>}
          </section>

          {/* Step 2 */}
          <section className="rounded-lg border border-border p-4">
            <h3 className="text-sm font-medium text-foreground">2. Create an application at your identity provider</h3>
            <p className="mt-1 text-xs text-muted-foreground">
              Create an OpenID Connect web application and give it this redirect address. Then copy its issuer, client ID
              and client secret into step 3.
            </p>
            <div className="mt-3">
              <CopyValue label="Redirect" value={state.redirect_uri} />
            </div>
          </section>

          {/* Step 3 */}
          <section className="rounded-lg border border-border p-4">
            <h3 className="text-sm font-medium text-foreground">3. Connect and turn on</h3>
            <div className="mt-3 space-y-3">
              <div>
                <label htmlFor="sso-issuer" className="mb-1 block text-xs text-muted-foreground">Issuer address</label>
                <Input id="sso-issuer" value={issuer} onChange={(e) => setIssuer(e.target.value)} className="h-9 text-sm"
                  placeholder="https://login.microsoftonline.com/your-tenant-id/v2.0" autoComplete="off" />
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label htmlFor="sso-client" className="mb-1 block text-xs text-muted-foreground">Client ID</label>
                  <Input id="sso-client" value={clientId} onChange={(e) => setClientId(e.target.value)} className="h-9 text-sm" autoComplete="off" />
                </div>
                <div>
                  <label htmlFor="sso-secret" className="mb-1 block text-xs text-muted-foreground">Client secret</label>
                  <Input id="sso-secret" type="password" value={secret} onChange={(e) => setSecret(e.target.value)} className="h-9 text-sm"
                    autoComplete="new-password" placeholder={state.config?.has_secret ? "Leave blank to keep the current one" : ""} />
                </div>
              </div>
              <label className="flex cursor-pointer items-start gap-2 text-xs text-foreground">
                <input type="checkbox" className="mt-0.5 h-3.5 w-3.5 accent-[hsl(var(--primary))]" checked={autoProvision}
                  onChange={(e) => setAutoProvision(e.target.checked)} />
                <span>
                  Create an account the first time someone from a verified domain signs in
                  <span className="block text-[11px] text-muted-foreground">Off means people must be invited first.</span>
                </span>
              </label>
              {autoProvision && (
                <div className="sm:w-1/2">
                  <label htmlFor="sso-role" className="mb-1 block text-xs text-muted-foreground">Role for new people</label>
                  <select id="sso-role" className={SELECT} value={role} onChange={(e) => setRole(e.target.value)}>
                    {state.roles.map((r) => <option key={r} value={r}>{ROLE_LABELS[r] || r}</option>)}
                  </select>
                </div>
              )}
              <label className={`flex items-start gap-2 text-xs ${hasVerified ? "cursor-pointer text-foreground" : "text-muted-foreground"}`}>
                <input type="checkbox" className="mt-0.5 h-3.5 w-3.5 accent-[hsl(var(--primary))]" checked={enabled} disabled={!hasVerified}
                  onChange={(e) => setEnabled(e.target.checked)} />
                <span>
                  Turn single sign-on on
                  {!hasVerified && <span className="block text-[11px]">Verify a domain in step 1 first.</span>}
                </span>
              </label>
              <label className={`flex items-start gap-2 text-xs ${enabled ? "cursor-pointer text-foreground" : "text-muted-foreground"}`}>
                <input type="checkbox" className="mt-0.5 h-3.5 w-3.5 accent-[hsl(var(--primary))]" checked={enabled && enforce} disabled={!enabled}
                  onChange={(e) => setEnforce(e.target.checked)} />
                <span>
                  Require single sign-on
                  <span className="block text-[11px] text-muted-foreground">
                    Members on your verified domains can no longer sign in with a password, Google or a passkey. The
                    organization owner always keeps password access, so a provider outage cannot lock you out. Try a
                    sign-in yourself before turning this on.
                  </span>
                </span>
              </label>

              {state.config?.last_error && !formNote && (
                <div className="flex items-start gap-1.5 text-[11px] text-yellow-500">
                  <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                  <span>Last sign-in problem: {state.config.last_error}</span>
                </div>
              )}
              {formNote && (
                <div role={formNote.ok ? "status" : "alert"}
                  className={`flex items-start gap-1.5 text-xs ${formNote.ok ? "text-green-500" : "text-destructive"}`}>
                  {formNote.ok ? <Check className="mt-0.5 h-3.5 w-3.5 shrink-0" /> : <X className="mt-0.5 h-3.5 w-3.5 shrink-0" />}
                  <span>{formNote.text}</span>
                </div>
              )}
              <div className="flex flex-wrap items-center gap-2 pt-1">
                {state.config && (confirmRemove ? (
                  <>
                    <Button size="sm" variant="destructive" className="h-8 text-xs" disabled={saving} onClick={removeAll}>
                      Remove single sign-on
                    </Button>
                    <Button size="sm" variant="outline" className="h-8 text-xs" onClick={() => setConfirmRemove(false)}>Keep</Button>
                  </>
                ) : (
                  <Button size="sm" variant="outline" className="h-8 text-xs" disabled={saving} onClick={() => setConfirmRemove(true)}>
                    Remove
                  </Button>
                ))}
                <div className="ml-auto flex gap-2">
                  {state.config && (
                    <Button size="sm" variant="outline" className="h-8 text-xs" disabled={saving} onClick={test}>
                      Check connection
                    </Button>
                  )}
                  <Button size="sm" className="h-8 text-xs" disabled={saving || !issuer.trim() || !clientId.trim()} onClick={save}>
                    {saving && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                    Save
                  </Button>
                </div>
              </div>
              {state.config?.last_login_at && (
                <p className="text-[11px] text-muted-foreground">
                  Last successful sign-in: {new Date(state.config.last_login_at).toLocaleString()}
                </p>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
