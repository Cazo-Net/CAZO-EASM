"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowUpRight,
  CreditCard,
  Globe,
  ExternalLink,
  FileText,
  Gauge,
  Info,
  Loader2,
  Plus,
  Receipt,
  Star,
  Trash2,
} from "lucide-react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PageHeader } from "@/components/common/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";
import {
  addPaymentMethod,
  billingErrorMessage,
  cancelPlan,
  formatMoney,
  getBillingOverview,
  LIMIT_LABELS,
  listInvoices,
  listPaymentMethods,
  openBillingPortal,
  removePaymentMethod,
  resumePlan,
  setDefaultPaymentMethod,
  type BillingOverview,
  type Invoice,
  type LimitKey,
  type PaymentMethod,
} from "@/lib/api-billing";

const STATUS_LABEL: Record<string, { label: string; variant: "success" | "warning" | "destructive" | "secondary" }> = {
  active: { label: "Active", variant: "success" },
  trialing: { label: "Trial", variant: "success" },
  past_due: { label: "Payment overdue", variant: "warning" },
  canceled: { label: "Cancelled", variant: "destructive" },
  expired: { label: "Expired", variant: "destructive" },
  incomplete: { label: "Awaiting payment", variant: "warning" },
  none: { label: "Trial", variant: "secondary" },
};

function fmtDate(value: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

const METER_HINT: Record<LimitKey, string> = {
  root_domains: "Domains you have scanned or added as scopes",
  hosts: "Live hosts found across your root domains",
  users: "Members plus pending invitations",
  scans_per_month: "Resets on the 1st of each month (UTC)",
};

function Meter({ name, used, limit }: { name: LimitKey; used: number; limit: number | null }) {
  const pct = limit ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  const over = limit != null && used > limit;
  const full = limit != null && used >= limit;
  const tone = limit == null ? "bg-primary/50" : over ? "bg-red-500" : full ? "bg-amber-400" : pct >= 80 ? "bg-amber-400/80" : "bg-primary";
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span>{LIMIT_LABELS[name]}</span>
        <span className="font-mono text-xs text-muted-foreground">
          <span className={cn(over ? "text-red-400" : full ? "text-amber-400" : "text-foreground")}>
            {used.toLocaleString()}
          </span>{" "}
          / {limit == null ? "unlimited" : limit.toLocaleString()}
        </span>
      </div>
      <div
        className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-muted/40"
        role="meter"
        aria-label={LIMIT_LABELS[name]}
        aria-valuemin={0}
        aria-valuemax={limit ?? undefined}
        aria-valuenow={used}
      >
        <div className={cn("h-full rounded-full transition-all", tone)} style={{ width: `${limit == null ? 100 : Math.max(pct, used > 0 ? 2 : 0)}%` }} />
      </div>
      <p className={cn("mt-1 text-[11px]", over ? "text-red-400" : full ? "text-amber-400" : "text-muted-foreground")}>
        {over
          ? `Over your plan by ${(used - (limit as number)).toLocaleString()}`
          : full
            ? "Limit reached"
            : METER_HINT[name]}
      </p>
    </div>
  );
}

const SALES_EMAIL = process.env.NEXT_PUBLIC_SALES_EMAIL || "sales@cazoeasm.io";

function BillingInner() {
  const params = useSearchParams();
  const { user } = useAuth();
  const canManage = user?.role === "owner" || user?.role === "admin";

  const [overview, setOverview] = useState<BillingOverview | null>(null);
  const [methods, setMethods] = useState<PaymentMethod[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string>("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(
    params.get("updated") ? "Your plan was updated." : params.get("payment_method") ? "Payment method added." : ""
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const o = await getBillingOverview();
      setOverview(o);
      if (canManage) {
        const [m, i] = await Promise.all([
          o.checkout_enabled ? listPaymentMethods().catch(() => []) : Promise.resolve([]),
          listInvoices().catch(() => []),
        ]);
        setMethods(m);
        setInvoices(i);
      }
    } catch (e) {
      setError(billingErrorMessage(e, "Could not load billing."));
    } finally {
      setLoading(false);
    }
  }, [canManage]);

  useEffect(() => {
    if (user?.organization_id) load();
    else setLoading(false);
  }, [load, user?.organization_id]);

  async function run(key: string, fn: () => Promise<unknown>, done?: string) {
    setBusy(key);
    setError("");
    try {
      await fn();
      if (done) setNotice(done);
      await load();
    } catch (e) {
      setError(billingErrorMessage(e));
    } finally {
      setBusy("");
    }
  }

  async function redirect(key: string, fn: () => Promise<string>) {
    setBusy(key);
    setError("");
    try {
      window.location.href = await fn();
    } catch (e) {
      setError(billingErrorMessage(e));
      setBusy("");
    }
  }

  if (!user?.organization_id) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <PageHeader title="Billing" />
        <p className="text-sm text-muted-foreground">
          Create an organization in{" "}
          <Link href="/settings/organization" className="text-primary underline">Organization settings</Link>{" "}
          before choosing a plan.
        </p>
      </div>
    );
  }

  if (loading && !overview) {
    return (
      <div className="flex justify-center py-24">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const o = overview;
  const isTrial = !o || o.plan.id === "free";
  const status = isTrial
    ? o?.status === "expired"
      ? STATUS_LABEL.expired
      : { label: "Free trial", variant: "secondary" as const }
    : STATUS_LABEL[o?.status ?? "none"] ?? STATUS_LABEL.none;
  const isPaid = o && o.plan.id !== "free" && ["active", "trialing", "past_due"].includes(o.status);
  const managed = !!o?.managed_by_staff;
  const paused = o?.root_domains.filter((d) => !d.active) ?? [];
  const atLimit = o
    ? (Object.keys(o.usage) as LimitKey[]).filter((k) => o.usage[k].limit != null && o.usage[k].used >= (o.usage[k].limit as number))
    : [];

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <PageHeader
        title="Billing & plan"
        description="Your plan, usage, payment methods and invoices."
        breadcrumbs={[{ label: "Settings", href: "/settings" }, { label: "Billing" }]}
        actions={
          canManage && o?.has_customer && o.checkout_enabled ? (
            <Button variant="outline" size="sm" disabled={!!busy} onClick={() => redirect("portal", openBillingPortal)}>
              {busy === "portal" ? <Loader2 className="h-4 w-4 animate-spin" /> : <ExternalLink className="h-4 w-4" />}
              Open Stripe billing portal
            </Button>
          ) : null
        }
      />

      {o?.test_mode && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
          Test mode: payments use Stripe test cards and no real money moves.
        </div>
      )}
      {notice && (
        <div className="rounded-xl border border-border bg-muted/40 p-3 text-sm">{notice}</div>
      )}
      {error && (
        <div className="rounded-xl border border-red-500/40 bg-destructive/10 p-3 text-sm">{error}</div>
      )}
      {o && (paused.length > 0 || atLimit.length > 0) && (
        <div className="flex flex-col gap-3 rounded-xl border border-amber-500/40 bg-amber-500/[0.08] p-4 text-sm sm:flex-row sm:items-center sm:justify-between">
          <div className="flex gap-3">
            <Gauge className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
            <div>
              <p className="font-medium">
                {paused.length > 0
                  ? `${paused.length} root domain${paused.length === 1 ? " is" : "s are"} paused`
                  : `You have reached your ${o.plan.name} plan limit`}
              </p>
              <p className="mt-0.5 text-muted-foreground">
                {paused.length > 0
                  ? `Your organization has more root domains than the ${o.plan.name} plan covers. The oldest ${o.usage.root_domains.limit} keep scanning; ${paused.map((d) => d.domain).join(", ")} will not scan until you upgrade or remove domains.`
                  : `Limit reached for ${atLimit.map((k) => LIMIT_LABELS[k].toLowerCase()).join(", ")}. New ones will be refused until you upgrade${atLimit.includes("scans_per_month") ? " or the month resets" : ""}.`}
              </p>
            </div>
          </div>
          {canManage && !managed && (
            <Button asChild size="sm" className="shrink-0">
              <Link href={`/billing/checkout?plan=${isPaid ? o.plan.id : "essentials"}`}>
                {isPaid ? "Upgrade" : "Choose a plan"} <ArrowUpRight className="h-4 w-4" />
              </Link>
            </Button>
          )}
        </div>
      )}
      {managed && (
        <div className="flex gap-2 rounded-xl border border-border bg-muted/30 p-3 text-sm">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
          <span>
            Your plan is managed by CAZO and invoiced directly. To change it, contact{" "}
            <a className="text-primary underline" href={`mailto:${SALES_EMAIL}?subject=CAZO%20EASM%20plan%20change`}>
              {SALES_EMAIL}
            </a>
            .
          </span>
        </div>
      )}
      {o?.last_payment_error && (
        <div className="flex gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
          <span>{o.last_payment_error}</span>
        </div>
      )}

      {o && (
        <div className="grid gap-6 lg:grid-cols-2">
          <SectionCard title="Current plan" icon={<Star className="h-4 w-4" />} accent="brand">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-2xl font-semibold">{o.plan.name}</p>
                <p className="text-sm text-muted-foreground">
                  {o.plan.per_client ? `${o.clients} client organizations` : o.plan.tagline}
                  {o.extra_domains ? ` · +${o.extra_domains} extra root domains` : ""}
                </p>
              </div>
              <Badge variant={status.variant}>{status.label}</Badge>
            </div>

            <dl className="mt-5 grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-xs text-muted-foreground">Billing</dt>
                <dd>
                  {isTrial
                    ? "Free, no card needed"
                    : o.payment_mode === "subscription"
                    ? `Auto-renew, ${o.interval === "quarter" ? "quarterly" : "annually"}`
                    : o.payment_mode === "prepaid"
                      ? `Prepaid ${o.interval === "quarter" ? "quarter" : "year"}`
                      : o.payment_mode === "manual"
                        ? "Invoiced by CAZO"
                        : "Free trial"}
                </dd>
              </div>
              {!isTrial && (
                <div>
                  <dt className="text-xs text-muted-foreground">
                    {o.cancel_at_period_end || o.payment_mode !== "subscription" ? "Ends on" : "Renews on"}
                  </dt>
                  <dd>{o.current_period_end ? fmtDate(o.current_period_end) : "No end date"}</dd>
                </div>
              )}
              <div>
                <dt className="text-xs text-muted-foreground">Scheduled scans</dt>
                <dd className="capitalize">{o.plan.scan_frequency}</dd>
              </div>
              {isTrial && (
                <div>
                  <dt className="text-xs text-muted-foreground">Upgrade</dt>
                  <dd>Any time, takes effect at once</dd>
                </div>
              )}
            </dl>

            {!canManage && (
              <p className="mt-6 text-xs text-muted-foreground">Only an organization owner or admin can change the plan.</p>
            )}
            {canManage && managed && (
              <div className="mt-6 flex flex-wrap gap-2">
                <Button asChild size="sm" variant="outline">
                  <a href={`mailto:${SALES_EMAIL}?subject=CAZO%20EASM%20plan%20change`}>Contact CAZO</a>
                </Button>
                <Button asChild size="sm" variant="ghost">
                  <Link href="/pricing">Compare plans</Link>
                </Button>
              </div>
            )}
            {canManage && !managed && (
              <div className="mt-6 flex flex-wrap gap-2">
                <Button asChild size="sm">
                  <Link href={`/billing/checkout?plan=${isPaid ? o.plan.id : "essentials"}`}>
                    {isPaid ? "Change plan" : "Choose a plan"}
                  </Link>
                </Button>
                {isPaid && o.payment_mode === "prepaid" && (
                  <Button asChild size="sm" variant="outline">
                    <Link href={`/billing/checkout?plan=${o.plan.id}&interval=${o.interval ?? "year"}`}>Renew term</Link>
                  </Button>
                )}
                {isPaid && o.payment_mode === "subscription" && !o.cancel_at_period_end && (
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={!!busy}
                    onClick={() => {
                      if (window.confirm(`Cancel at the end of the term on ${fmtDate(o.current_period_end)}? You keep access until then.`)) {
                        run("cancel", cancelPlan, "Your plan will not renew.");
                      }
                    }}
                  >
                    {busy === "cancel" && <Loader2 className="h-4 w-4 animate-spin" />}
                    Cancel renewal
                  </Button>
                )}
                {isPaid && o.payment_mode === "subscription" && o.cancel_at_period_end && (
                  <Button size="sm" variant="outline" disabled={!!busy} onClick={() => run("resume", resumePlan, "Your plan will renew.")}>
                    {busy === "resume" && <Loader2 className="h-4 w-4 animate-spin" />}
                    Keep my plan
                  </Button>
                )}
                <Button asChild size="sm" variant="ghost">
                  <Link href="/pricing">Compare plans</Link>
                </Button>
              </div>
            )}
          </SectionCard>

          <SectionCard title="Usage" icon={<Gauge className="h-4 w-4" />}>
            <div className="space-y-4">
              {(Object.keys(o.usage) as LimitKey[]).map((k) => (
                <Meter key={k} name={k} used={o.usage[k].used} limit={o.usage[k].limit} />
              ))}
            </div>
          </SectionCard>
        </div>
      )}

      {o && (
        <SectionCard
          title="Root domains"
          description="Each registrable domain (example.com) counts once, with all its subdomains."
          icon={<Globe className="h-4 w-4" />}
          actions={
            <Button asChild size="sm" variant="outline">
              <Link href="/scopes">Manage scopes</Link>
            </Button>
          }
        >
          {o.root_domains.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No root domains yet. Add one on the{" "}
              <Link href="/scopes" className="text-primary underline">Scopes</Link> page or{" "}
              <Link href="/scan/new" className="text-primary underline">start a scan</Link>.
            </p>
          ) : (
            <ul className="divide-y divide-border/40">
              {o.root_domains.map((d) => (
                <li key={d.domain} className="flex items-center justify-between gap-3 py-2.5">
                  <div className="min-w-0">
                    <p className="truncate font-mono text-sm">{d.domain}</p>
                    <p className="text-[11px] text-muted-foreground">Added {fmtDate(d.first_seen)}</p>
                  </div>
                  {d.active ? (
                    <Badge variant="success">Active</Badge>
                  ) : (
                    <Badge variant="warning">Paused, over plan</Badge>
                  )}
                </li>
              ))}
            </ul>
          )}
          {paused.length > 0 && (
            <p className="mt-3 text-[11px] text-muted-foreground">
              The oldest domains up to your allowance stay active. To free a slot, remove the domain&apos;s scopes and
              scans, or add extra root domains to your plan.
            </p>
          )}
        </SectionCard>
      )}

      {canManage && o && (
        <SectionCard
          title="Payment methods"
          icon={<CreditCard className="h-4 w-4" />}
          actions={
            o.checkout_enabled ? (
              <Button size="sm" variant="outline" disabled={!!busy} onClick={() => redirect("add-pm", addPaymentMethod)}>
                {busy === "add-pm" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                Add card
              </Button>
            ) : null
          }
        >
          {!o.checkout_enabled ? (
            <p className="text-sm text-muted-foreground">Online payments are not switched on yet.</p>
          ) : methods.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No saved payment methods. A card is saved when you start an auto-renewing plan; one-off
              payments such as FPX are not stored.
            </p>
          ) : (
            <ul className="divide-y divide-border/40">
              {methods.map((m) => (
                <li key={m.id} className="flex items-center justify-between gap-3 py-3">
                  <div className="flex items-center gap-3">
                    <CreditCard className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="text-sm capitalize">
                        {m.brand} {m.last4 ? `•••• ${m.last4}` : ""}
                        {m.is_default && <Badge variant="secondary" className="ml-2">Default</Badge>}
                      </p>
                      {m.exp_month && (
                        <p className="font-mono text-[11px] text-muted-foreground">
                          Expires {String(m.exp_month).padStart(2, "0")}/{m.exp_year}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-1">
                    {!m.is_default && (
                      <Button size="sm" variant="ghost" disabled={!!busy} onClick={() => run(`def-${m.id}`, () => setDefaultPaymentMethod(m.id), "Default payment method updated.")}>
                        Make default
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-label="Remove payment method"
                      disabled={!!busy || (m.is_default && methods.length > 1)}
                      onClick={() => {
                        if (window.confirm("Remove this payment method?")) {
                          run(`rm-${m.id}`, () => removePaymentMethod(m.id), "Payment method removed.");
                        }
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>
      )}

      {canManage && (
        <SectionCard title="Invoices and receipts" icon={<Receipt className="h-4 w-4" />}>
          {invoices.length === 0 ? (
            <p className="text-sm text-muted-foreground">No invoices yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-muted-foreground">
                    <th className="pb-2 font-normal">Date</th>
                    <th className="pb-2 font-normal">Description</th>
                    <th className="pb-2 font-normal">Amount</th>
                    <th className="pb-2 font-normal">Status</th>
                    <th className="pb-2" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {invoices.map((inv) => (
                    <tr key={inv.id}>
                      <td className="py-2.5 font-mono text-xs">{fmtDate(inv.paid_at || inv.created_at)}</td>
                      <td className="py-2.5">
                        {inv.description}
                        {inv.number && <span className="ml-2 font-mono text-[11px] text-muted-foreground">{inv.number}</span>}
                      </td>
                      <td className="py-2.5 font-mono">{formatMoney(inv.amount, inv.currency)}</td>
                      <td className="py-2.5">
                        <Badge variant={inv.status === "paid" ? "success" : inv.status === "failed" ? "destructive" : "secondary"}>
                          {inv.status}
                        </Badge>
                      </td>
                      <td className="py-2.5 text-right">
                        {(inv.pdf_url || inv.hosted_url) && (
                          <a
                            href={inv.pdf_url || inv.hosted_url || "#"}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                          >
                            <FileText className="h-3.5 w-3.5" /> {inv.pdf_url ? "PDF" : "View"}
                          </a>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      )}
    </div>
  );
}

export default function BillingPage() {
  return (
    <ProtectedRoute>
      <Suspense fallback={null}>
        <BillingInner />
      </Suspense>
    </ProtectedRoute>
  );
}
