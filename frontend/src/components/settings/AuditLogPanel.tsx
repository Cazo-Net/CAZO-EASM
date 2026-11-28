"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import {
  ScrollText,
  Download,
  ShieldCheck,
  ShieldAlert,
  Loader2,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Search,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

interface AuditEntry {
  id: string;
  seq: number | null;
  action: string;
  status: string | null;
  actor_id: string | null;
  actor_type: string | null;
  actor_email: string | null;
  target_type: string | null;
  target_id: string | null;
  detail: Record<string, unknown>;
  ip_address: string | null;
  user_agent: string | null;
  request_id: string | null;
  created_at: string | null;
  hash: string | null;
}

interface VerifyResult {
  valid: boolean;
  checked: number;
  legacy_unverified: number;
  last_hash: string | null;
  verified_at: string;
  problem: { seq: number; reason: string; message: string } | null;
}

const PAGE_SIZE = 50;

/** Plain-English names for the actions people look for most. */
const ACTION_LABELS: Record<string, string> = {
  "auth.login_success": "Signed in",
  "auth.login_failed": "Failed sign-in",
  "auth.account_locked": "Account locked",
  "auth.user_registered": "Account created",
  "auth.mfa_enabled": "Two-factor turned on",
  "auth.mfa_disabled": "Two-factor turned off",
  "auth.recovery_codes_generated": "Recovery codes generated",
  "auth.password_changed": "Password changed",
  "auth.password_reset_requested": "Password reset requested",
  "auth.password_reset_completed": "Password reset",
  "auth.email_change_requested": "Email change requested",
  "auth.email_verified": "Email verified",
  "auth.session_revoked": "Session signed out",
  "auth.all_sessions_revoked": "All sessions signed out",
  "auth.invitation_sent": "Member invited",
  "auth.invitation_accepted": "Invitation accepted",
  "member.invitation_revoked": "Invitation withdrawn",
  "org.create": "Organization created",
  "org.update": "Organization settings changed",
  "org.delete": "Organization deleted",
  "org.member.role_changed": "Member role changed",
  "org.member.removed": "Member removed",
  "user.delete_account": "Account deleted",
  "api_key.create": "API key created",
  "api_key.update": "API key changed",
  "api_key.rotate": "API key rotated",
  "api_key.revoke": "API key revoked",
  "webhook.create": "Webhook added",
  "webhook.update": "Webhook changed",
  "webhook.delete": "Webhook removed",
  "scan.create": "Scan started",
  "scan.create.denied": "Scan refused (out of scope)",
  "scan.cancel": "Scan cancelled",
  "scan.delete": "Scan deleted",
  "scan.schedule.create": "Scheduled scan added",
  "scan.schedule.delete": "Scheduled scan stopped",
  "report.generate": "Report generated",
  "report.download": "Report downloaded",
  "report.delete": "Report deleted",
  "billing.checkout_started": "Checkout started",
  "billing.cancel_requested": "Subscription cancellation requested",
  "billing.cancel_withdrawn": "Subscription cancellation withdrawn",
  "billing.plan_set_by_staff": "Plan set by CAZO staff",
  "audit.export": "Audit log exported",
};

const CATEGORIES = [
  { value: "", label: "All activity" },
  { value: "auth.*", label: "Sign-in & security" },
  { value: "org.*", label: "Organization & members" },
  { value: "api_key.*", label: "API keys" },
  { value: "webhook.*", label: "Webhooks" },
  { value: "scan.*", label: "Scans" },
  { value: "scope.*", label: "Scope" },
  { value: "report.*", label: "Reports" },
  { value: "billing.*", label: "Billing" },
  { value: "audit.*", label: "Audit log exports" },
];

function token(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("access_token") || sessionStorage.getItem("access_token") || "";
}

function label(action: string): string {
  return ACTION_LABELS[action] || action;
}

function when(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return isNaN(d.getTime()) ? iso : d.toLocaleString();
}

export function AuditLogPanel() {
  const [items, setItems] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [category, setCategory] = useState("");
  const [actor, setActor] = useState("");
  const [actorInput, setActorInput] = useState("");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [verify, setVerify] = useState<VerifyResult | null>(null);
  const [exporting, setExporting] = useState<string | null>(null);

  const filterParams = useCallback(() => {
    const p = new URLSearchParams();
    if (category) p.set("action", category);
    if (actor) p.set("actor", actor);
    if (since) p.set("since", new Date(since + "T00:00:00").toISOString());
    if (until) p.set("until", new Date(until + "T23:59:59.999").toISOString());
    return p;
  }, [category, actor, since, until]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const p = filterParams();
      p.set("limit", String(PAGE_SIZE));
      p.set("offset", String(page * PAGE_SIZE));
      const res = await fetch(`/api/v1/audit-logs?${p.toString()}`, {
        headers: { Authorization: `Bearer ${token()}` },
      });
      if (res.status === 403) {
        setError("Only owners, administrators and security managers can view the audit log.");
        setItems([]);
        setTotal(0);
      } else if (res.status === 404) {
        setError("Create or join an organization to get an audit log.");
        setItems([]);
        setTotal(0);
      } else if (!res.ok) {
        setError("The audit log could not be loaded. Please try again.");
      } else {
        const data = await res.json();
        setItems(data.items || []);
        setTotal(data.total || 0);
      }
    } catch {
      setError("The audit log could not be loaded. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [filterParams, page]);

  useEffect(() => {
    load();
  }, [load]);

  const runVerify = useCallback(async () => {
    setVerifying(true);
    try {
      const res = await fetch("/api/v1/audit-logs/verify", {
        headers: { Authorization: `Bearer ${token()}` },
      });
      if (res.ok) setVerify(await res.json());
    } catch {
      // leave the previous result in place
    } finally {
      setVerifying(false);
    }
  }, []);

  const runExport = useCallback(
    async (format: "csv" | "jsonl") => {
      setExporting(format);
      try {
        const p = filterParams();
        p.set("format", format);
        const res = await fetch(`/api/v1/audit-logs/export?${p.toString()}`, {
          headers: { Authorization: `Bearer ${token()}` },
        });
        if (!res.ok) {
          setError("The export failed. Please try again.");
          return;
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `audit-log-${new Date().toISOString().slice(0, 10)}.${format}`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        load(); // the export itself is now an entry
      } catch {
        setError("The export failed. Please try again.");
      } finally {
        setExporting(null);
      }
    },
    [filterParams, load]
  );

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const resetPage = () => setPage(0);

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <ScrollText className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-foreground">Audit log</h2>
            <p className="text-xs text-muted-foreground">
              Who did what in your organization, and when. Entries cannot be edited or removed without it showing.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" className="h-8 text-xs" onClick={runVerify} disabled={verifying}>
            {verifying ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <ShieldCheck className="h-3.5 w-3.5 mr-1.5" />}
            Check integrity
          </Button>
          <Button size="sm" variant="outline" className="h-8 text-xs" onClick={() => runExport("csv")} disabled={!!exporting}>
            {exporting === "csv" ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <Download className="h-3.5 w-3.5 mr-1.5" />}
            CSV
          </Button>
          <Button size="sm" variant="outline" className="h-8 text-xs" onClick={() => runExport("jsonl")} disabled={!!exporting}>
            {exporting === "jsonl" ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <Download className="h-3.5 w-3.5 mr-1.5" />}
            JSON
          </Button>
        </div>
      </div>

      {verify && (
        <div
          role="status"
          className={`mb-4 flex items-start gap-2 rounded-lg border px-3 py-2 text-xs ${
            verify.valid
              ? "border-green-500/30 bg-green-500/5 text-foreground"
              : "border-destructive/40 bg-destructive/5 text-foreground"
          }`}
        >
          {verify.valid ? (
            <ShieldCheck className="h-4 w-4 shrink-0 text-green-500 mt-0.5" />
          ) : (
            <ShieldAlert className="h-4 w-4 shrink-0 text-destructive mt-0.5" />
          )}
          <div>
            {verify.valid ? (
              <p>
                <span className="font-medium">Intact.</span> All {verify.checked.toLocaleString()} entries were checked
                and none has been changed or removed.
                {verify.legacy_unverified > 0 &&
                  ` ${verify.legacy_unverified.toLocaleString()} older entries were written before integrity checking existed and are not covered.`}
              </p>
            ) : (
              <p>
                <span className="font-medium">Integrity check failed.</span> {verify.problem?.message} Entries before it
                ({verify.checked.toLocaleString()}) are intact. Contact support.
              </p>
            )}
            {verify.last_hash && (
              <p className="mt-1 text-muted-foreground break-all">
                Latest fingerprint: <span className="font-mono">{verify.last_hash}</span>
              </p>
            )}
          </div>
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="audit-category" className="text-xs text-muted-foreground mb-1 block">Activity</label>
          <select
            id="audit-category"
            value={category}
            onChange={(e) => { setCategory(e.target.value); resetPage(); }}
            className="h-9 rounded-md border border-border bg-muted/30 px-2 text-sm text-foreground"
          >
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
        </div>
        <form
          onSubmit={(e) => { e.preventDefault(); setActor(actorInput.trim()); resetPage(); }}
          className="flex items-end gap-2"
        >
          <div>
            <label htmlFor="audit-actor" className="text-xs text-muted-foreground mb-1 block">Person</label>
            <div className="relative">
              <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="audit-actor"
                value={actorInput}
                onChange={(e) => setActorInput(e.target.value)}
                onBlur={() => { if (actorInput.trim() !== actor) { setActor(actorInput.trim()); resetPage(); } }}
                placeholder="Email"
                className="h-9 w-48 pl-7 text-sm"
              />
            </div>
          </div>
        </form>
        <div>
          <label htmlFor="audit-since" className="text-xs text-muted-foreground mb-1 block">From</label>
          <Input id="audit-since" type="date" value={since} max={until || undefined}
            onChange={(e) => { setSince(e.target.value); resetPage(); }} className="h-9 text-sm" />
        </div>
        <div>
          <label htmlFor="audit-until" className="text-xs text-muted-foreground mb-1 block">To</label>
          <Input id="audit-until" type="date" value={until} min={since || undefined}
            onChange={(e) => { setUntil(e.target.value); resetPage(); }} className="h-9 text-sm" />
        </div>
      </div>

      {error && (
        <div role="alert" className="mb-4 rounded-lg border border-border bg-muted/20 px-3 py-2 text-sm text-muted-foreground">
          {error}
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/20 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
              <th className="px-3 py-2 font-semibold">When</th>
              <th className="px-3 py-2 font-semibold">Who</th>
              <th className="px-3 py-2 font-semibold">What</th>
              <th className="px-3 py-2 font-semibold">From</th>
              <th className="px-3 py-2 w-8" />
            </tr>
          </thead>
          <tbody>
            {loading && items.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-3 py-10 text-center">
                  <Loader2 className="mx-auto h-5 w-5 animate-spin text-muted-foreground" />
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-3 py-10 text-center text-sm text-muted-foreground">
                  {error ? "" : "No activity matches these filters."}
                </td>
              </tr>
            ) : (
              items.map((e) => {
                const isOpen = open === e.id;
                const failed = e.status && e.status !== "success";
                return (
                  <Fragment key={e.id}>
                    <tr
                      className="border-b border-border last:border-0 hover:bg-muted/20 cursor-pointer"
                      onClick={() => setOpen(isOpen ? null : e.id)}
                    >
                      <td className="px-3 py-2 whitespace-nowrap text-xs text-muted-foreground">{when(e.created_at)}</td>
                      <td className="px-3 py-2 text-xs">
                        {e.actor_email || (e.actor_type === "system" ? "System" : e.actor_id || "System")}
                        {e.actor_type === "staff" && <Badge variant="outline" className="ml-1.5 text-[10px]">CAZO staff</Badge>}
                      </td>
                      <td className="px-3 py-2">
                        <span className="text-foreground">{label(e.action)}</span>
                        {failed && (
                          <Badge variant="outline" className="ml-2 border-destructive/40 text-[10px] text-destructive">
                            {e.status}
                          </Badge>
                        )}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap font-mono text-xs text-muted-foreground">{e.ip_address || "—"}</td>
                      <td className="px-3 py-2 text-muted-foreground">
                        <button
                          type="button"
                          aria-expanded={isOpen}
                          aria-label={isOpen ? "Hide details" : "Show details"}
                          onClick={(ev) => { ev.stopPropagation(); setOpen(isOpen ? null : e.id); }}
                        >
                          <ChevronDown className={`h-4 w-4 transition-transform ${isOpen ? "rotate-180" : ""}`} />
                        </button>
                      </td>
                    </tr>
                    {isOpen && (
                      <tr className="border-b border-border bg-muted/10">
                        <td colSpan={5} className="px-3 py-3">
                          <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 text-xs sm:grid-cols-[max-content_1fr]">
                            <dt className="text-muted-foreground">Action</dt>
                            <dd className="font-mono break-all">{e.action}</dd>
                            {e.target_type && (
                              <>
                                <dt className="text-muted-foreground">Target</dt>
                                <dd className="font-mono break-all">{e.target_type}{e.target_id ? ` · ${e.target_id}` : ""}</dd>
                              </>
                            )}
                            {Object.keys(e.detail || {}).filter((k) => k !== "target_id_full").length > 0 && (
                              <>
                                <dt className="text-muted-foreground">Details</dt>
                                <dd className="font-mono break-all whitespace-pre-wrap">
                                  {Object.entries(e.detail)
                                    .filter(([k]) => k !== "target_id_full")
                                    .map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
                                    .join("\n")}
                                </dd>
                              </>
                            )}
                            {e.user_agent && (
                              <>
                                <dt className="text-muted-foreground">Browser</dt>
                                <dd className="break-all">{e.user_agent}</dd>
                              </>
                            )}
                            <dt className="text-muted-foreground">Entry</dt>
                            <dd className="font-mono break-all">
                              {e.seq ? `#${e.seq}` : "Older entry (not covered by integrity checking)"}
                              {e.hash ? ` · ${e.hash}` : ""}
                            </dd>
                          </dl>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
        <span>{total.toLocaleString()} {total === 1 ? "entry" : "entries"}</span>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" className="h-7 px-2" disabled={page === 0 || loading}
            onClick={() => setPage((p) => Math.max(0, p - 1))} aria-label="Previous page">
            <ChevronLeft className="h-3.5 w-3.5" />
          </Button>
          <span>Page {page + 1} of {pages}</span>
          <Button size="sm" variant="outline" className="h-7 px-2" disabled={page + 1 >= pages || loading}
            onClick={() => setPage((p) => p + 1)} aria-label="Next page">
            <ChevronRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}
