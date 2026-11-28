"use client";

import * as React from "react";
import { Loader2, Mail, Bell, Info, Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getAlertSettings, updateAlertSettings, type AlertSettings } from "@/lib/api-inventory";
import { Toggle } from "./shared";

const selectCls =
  "h-9 rounded-md border border-border bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50";

export function AlertSettingsPanel() {
  const [cfg, setCfg] = React.useState<AlertSettings | null>(null);
  const [saved, setSaved] = React.useState<string>("");
  const [error, setError] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [justSaved, setJustSaved] = React.useState(false);
  const [emailDraft, setEmailDraft] = React.useState("");

  const snapshot = (c: AlertSettings) =>
    JSON.stringify([c.enabled, c.rules, c.cert_expiry_days, c.finding_min_severity, c.recipients, c.extra_emails]);

  React.useEffect(() => {
    getAlertSettings()
      .then((c) => {
        setCfg(c);
        setSaved(snapshot(c));
      })
      .catch(() => setError("Alert settings could not be loaded."));
  }, []);

  if (!cfg) {
    return error ? (
      <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>
    ) : (
      <div className="flex items-center justify-center py-20 text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading alert settings…
      </div>
    );
  }

  const ro = !cfg.can_edit;
  const dirty = snapshot(cfg) !== saved;
  const patch = (p: Partial<AlertSettings>) => {
    setJustSaved(false);
    setCfg({ ...cfg, ...p });
  };
  const setRule = (key: string, channel: "in_app" | "email", value: boolean) =>
    patch({ rules: { ...cfg.rules, [key]: { ...cfg.rules[key], [channel]: value } } });

  const addEmail = () => {
    const value = emailDraft.trim().toLowerCase();
    if (!value) return;
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value)) {
      setError(`"${emailDraft}" is not a valid email address.`);
      return;
    }
    if (cfg.extra_emails.length >= cfg.max_extra_emails) {
      setError(`You can add up to ${cfg.max_extra_emails} extra addresses.`);
      return;
    }
    setError("");
    if (!cfg.extra_emails.includes(value)) patch({ extra_emails: [...cfg.extra_emails, value] });
    setEmailDraft("");
  };

  const save = async () => {
    setSaving(true);
    setError("");
    try {
      const next = await updateAlertSettings({
        enabled: cfg.enabled,
        rules: cfg.rules,
        cert_expiry_days: cfg.cert_expiry_days,
        finding_min_severity: cfg.finding_min_severity,
        recipients: cfg.recipients,
        extra_emails: cfg.extra_emails,
      });
      setCfg(next);
      setSaved(snapshot(next));
      setJustSaved(true);
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Alert settings could not be saved. Your changes are still here.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-[860px] space-y-5">
      {ro && (
        <p className="flex items-start gap-2 rounded-lg border border-border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
          <Info className="mt-0.5 h-4 w-4 shrink-0" />
          Only owners and admins can change these. You can mute alerts for yourself under Settings, Notifications.
        </p>
      )}
      {!cfg.email_delivery.configured && (
        <p className="flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm">
          <Mail className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
          <span>
            Email is not connected on this deployment yet, so alerts only appear in the app. In-app alerts work now;
            email starts as soon as a mail provider is configured.
          </span>
        </p>
      )}

      <section className="rounded-xl border border-border bg-card">
        <div className="flex items-center justify-between gap-4 border-b border-border px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold">Change alerts</h2>
            <p className="mt-0.5 text-[13px] text-muted-foreground">
              One alert per kind of change per scan. History is kept even when alerts are off.
            </p>
          </div>
          <Toggle checked={cfg.enabled} onChange={(v) => patch({ enabled: v })} disabled={ro} label="Change alerts" />
        </div>

        <div className={cfg.enabled ? "" : "pointer-events-none opacity-50"} aria-disabled={!cfg.enabled}>
          <div className="grid grid-cols-[1fr_64px_64px] items-center gap-x-2 px-5 pt-3 text-xs font-medium text-muted-foreground">
            <span>Alert</span>
            <span className="flex items-center justify-center gap-1">
              <Bell className="h-3.5 w-3.5" /> In app
            </span>
            <span className="flex items-center justify-center gap-1">
              <Mail className="h-3.5 w-3.5" /> Email
            </span>
          </div>
          <ul className="divide-y divide-border px-5">
            {cfg.alert_types.map((t) => (
              <li key={t.key} className="grid grid-cols-[1fr_64px_64px] items-center gap-x-2 py-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium">{t.label}</p>
                  <p className="text-[13px] text-muted-foreground">{t.description}</p>
                </div>
                <div className="flex justify-center">
                  <Toggle
                    checked={cfg.rules[t.key]?.in_app ?? false}
                    onChange={(v) => setRule(t.key, "in_app", v)}
                    disabled={ro || !cfg.enabled}
                    label={`${t.label}: in app`}
                  />
                </div>
                <div className="flex justify-center">
                  <Toggle
                    checked={cfg.rules[t.key]?.email ?? false}
                    onChange={(v) => setRule(t.key, "email", v)}
                    disabled={ro || !cfg.enabled}
                    label={`${t.label}: email`}
                  />
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card px-5 py-4">
        <h2 className="text-sm font-semibold">Thresholds</h2>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="text-[13px] text-muted-foreground">Warn about certificates expiring within</span>
            <span className="mt-1 flex items-center gap-2">
              <Input
                type="number"
                min={1}
                max={365}
                value={cfg.cert_expiry_days}
                disabled={ro}
                onChange={(e) =>
                  patch({ cert_expiry_days: Math.max(1, Math.min(365, Number(e.target.value) || 1)) })
                }
                className="h-9 w-24"
              />
              days
            </span>
          </label>
          <label className="block text-sm">
            <span className="text-[13px] text-muted-foreground">Alert on new findings rated</span>
            <span className="mt-1 block">
              <select
                className={selectCls}
                value={cfg.finding_min_severity}
                disabled={ro}
                onChange={(e) => patch({ finding_min_severity: e.target.value as AlertSettings["finding_min_severity"] })}
              >
                <option value="critical">Critical only</option>
                <option value="high">High and critical</option>
                <option value="medium">Medium and above</option>
              </select>
            </span>
          </label>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-card px-5 py-4">
        <h2 className="text-sm font-semibold">Who gets alerts</h2>
        <div className="mt-3 space-y-2">
          {(
            [
              ["admins", "Owners and admins", "The people who manage this organization."],
              ["all", "Everyone in the organization", "Every active member, including viewers."],
            ] as const
          ).map(([value, label, hint]) => (
            <label key={value} className="flex cursor-pointer items-start gap-3 rounded-lg border border-border px-3 py-2.5 has-[:checked]:border-primary/60 has-[:checked]:bg-primary/5">
              <input
                type="radio"
                name="recipients"
                className="mt-1 accent-[hsl(var(--primary))]"
                checked={cfg.recipients === value}
                disabled={ro}
                onChange={() => patch({ recipients: value })}
              />
              <span>
                <span className="block text-sm font-medium">{label}</span>
                <span className="block text-[13px] text-muted-foreground">{hint}</span>
              </span>
            </label>
          ))}
        </div>

        {!ro && (
          <div className="mt-4">
            <label htmlFor="extra-email" className="text-[13px] text-muted-foreground">
              Also email these addresses (a SOC inbox or a client contact, up to {cfg.max_extra_emails})
            </label>
            <div className="mt-1 flex gap-2">
              <Input
                id="extra-email"
                type="email"
                placeholder="soc@example.com"
                value={emailDraft}
                onChange={(e) => setEmailDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addEmail();
                  }
                }}
                className="h-9 max-w-xs"
              />
              <Button type="button" variant="outline" size="sm" className="h-9" onClick={addEmail}>
                Add
              </Button>
            </div>
            {cfg.extra_emails.length > 0 && (
              <ul className="mt-2 flex flex-wrap gap-2">
                {cfg.extra_emails.map((email) => (
                  <li key={email} className="inline-flex items-center gap-1 rounded-full border border-border bg-muted/40 py-0.5 pl-2.5 pr-1 font-mono text-xs">
                    {email}
                    <button
                      type="button"
                      aria-label={`Remove ${email}`}
                      onClick={() => patch({ extra_emails: cfg.extra_emails.filter((x) => x !== email) })}
                      className="rounded-full p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>

      {error && (
        <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </p>
      )}

      {!ro && (
        <div className="flex items-center gap-3">
          <Button onClick={save} disabled={!dirty || saving}>
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            Save alert settings
          </Button>
          {justSaved && !dirty && (
            <span className="inline-flex items-center gap-1 text-sm text-success" role="status">
              <Check className="h-4 w-4" /> Saved
            </span>
          )}
        </div>
      )}
    </div>
  );
}
