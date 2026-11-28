"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, ArrowLeft, CreditCard, Info, Landmark, Loader2, Lock, ShieldCheck } from "lucide-react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PageHeader } from "@/components/common/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { Button } from "@/components/ui/button";
import { ClientStepper, IntervalToggle } from "@/components/billing/PlanGrid";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";
import {
  billingErrorMessage,
  formatMoney,
  getBillingOverview,
  getPlans,
  getQuote,
  LIMIT_LABELS,
  MAX_CLIENTS,
  MAX_EXTRA_DOMAINS,
  METHOD_LABELS,
  overLimitConflicts,
  startCheckout,
  type BillingInterval,
  type BillingOverview,
  type PaymentChoice,
  type PlanCatalog,
  type Quote,
} from "@/lib/api-billing";

function CheckoutInner() {
  const params = useSearchParams();
  const router = useRouter();
  const { user } = useAuth();

  const [catalog, setCatalog] = useState<PlanCatalog | null>(null);
  const [overview, setOverview] = useState<BillingOverview | null>(null);
  const [planId, setPlanId] = useState(params.get("plan") || "business");
  const [interval, setBillingInterval] = useState<BillingInterval>(
    params.get("interval") === "quarter" ? "quarter" : "year"
  );
  const [clients, setClients] = useState(Number(params.get("clients")) || 10);
  const [extraDomains, setExtraDomains] = useState(0);
  const [payment, setPayment] = useState<PaymentChoice>("subscription");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [quoteError, setQuoteError] = useState("");
  const [acceptOver, setAcceptOver] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const canceled = params.get("canceled") === "1";

  const canManage = user?.role === "owner" || user?.role === "admin";

  useEffect(() => {
    Promise.all([getPlans(), getBillingOverview().catch(() => null)])
      .then(([c, o]) => {
        setCatalog(c);
        setOverview(o);
        // Start from what the organization already has, so "Change plan" does
        // not silently drop extra domains or clients the customer pays for.
        if (o && o.plan.id !== "free" && ["active", "trialing", "past_due"].includes(o.status)) {
          setExtraDomains(o.extra_domains || 0);
          if (o.plan.per_client && !params.get("clients")) setClients(o.clients);
          if (!params.get("interval") && o.interval) setBillingInterval(o.interval);
          if (o.payment_mode === "prepaid") setPayment("prepaid");
        }
      })
      .catch(() => setError("Could not load plans."));
  }, []);

  const plan = useMemo(() => catalog?.plans.find((p) => p.id === planId) ?? null, [catalog, planId]);
  // MSSP needs at least the minimum number of clients; other plans are one unit.
  const qty = plan?.per_client ? Math.min(MAX_CLIENTS, Math.max(clients, plan.min_quantity)) : 1;

  useEffect(() => {
    if (!plan) return;
    let cancelled = false;
    setQuoteError("");
    getQuote({ plan: plan.id, interval, clients: qty, extra_domains: extraDomains })
      .then((q) => !cancelled && setQuote(q))
      .catch((e) => {
        if (cancelled) return;
        setQuote(null);
        setQuoteError(billingErrorMessage(e, "This order cannot be priced right now."));
      });
    return () => {
      cancelled = true;
    };
  }, [plan, interval, qty, extraDomains]);

  useEffect(() => setAcceptOver(false), [planId, qty, extraDomains]);

  const currentIsPaid =
    !!overview && overview.plan.id !== "free" && ["active", "trialing", "past_due"].includes(overview.status);
  const managed = !!overview?.managed_by_staff;
  const conflicts = overLimitConflicts(overview?.usage, quote?.limits);
  const sameAsCurrent =
    currentIsPaid &&
    !!plan &&
    overview!.payment_mode === "subscription" &&
    payment === "subscription" &&
    overview!.plan.id === plan.id &&
    overview!.interval === interval &&
    (overview!.extra_domains || 0) === extraDomains &&
    (!plan.per_client || overview!.clients === qty);
  const prepaidSwitch =
    currentIsPaid && overview!.payment_mode === "prepaid" && payment === "prepaid" && !!plan && overview!.plan.id !== plan.id;
  const prepaidRenewal =
    currentIsPaid && overview!.payment_mode === "prepaid" && payment === "prepaid" && !!plan && overview!.plan.id === plan.id;

  const hasAutoRenew =
    overview?.payment_mode === "subscription" &&
    ["active", "trialing", "past_due"].includes(overview.status);

  async function submit() {
    if (!plan) return;
    setSubmitting(true);
    setError("");
    try {
      const res = await startCheckout({
        plan: plan.id,
        interval,
        clients: qty,
        extra_domains: extraDomains,
        payment,
        accept_over_limit: conflicts.length > 0 && acceptOver,
      });
      if (res.url) {
        window.location.href = res.url;
        return;
      }
      router.push("/billing?updated=1");
    } catch (e) {
      setError(billingErrorMessage(e, "Checkout could not be started."));
      setSubmitting(false);
    }
  }

  if (!catalog) {
    return (
      <div className="flex justify-center py-24">
        {error ? <p className="text-sm text-destructive">{error}</p> : <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />}
      </div>
    );
  }

  const months = catalog.intervals.find((i) => i.id === interval)?.months ?? 12;
  const selectedOption = catalog.payment_options.find((o) => o.id === payment);

  return (
    <div className="mx-auto max-w-5xl p-6">
      <PageHeader
        title="Checkout"
        description="Review your plan, then pay securely with Stripe."
        breadcrumbs={[{ label: "Billing", href: "/billing" }, { label: "Checkout" }]}
        actions={
          <Link href="/pricing" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" /> All plans
          </Link>
        }
      />

      {canceled && (
        <div className="mb-4 rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
          Checkout was cancelled. Nothing was charged.
        </div>
      )}
      {catalog.test_mode && (
        <div className="mb-4 rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
          Test mode. Use card 4242 4242 4242 4242 with any future date and CVC. No real money moves.
        </div>
      )}
      {!catalog.checkout_enabled && (
        <div className="mb-4 rounded-xl border border-border bg-card p-3 text-sm text-muted-foreground">
          Online payment is not switched on yet. Contact sales to start a plan.
        </div>
      )}
      {!user?.organization_id && (
        <div className="mb-4 rounded-xl border border-border bg-card p-3 text-sm">
          Create your organization first in{" "}
          <Link className="text-primary underline" href="/settings/organization">Organization settings</Link>.
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-6">
          <SectionCard title="Plan" icon={<ShieldCheck className="h-4 w-4" />}>
            <div className="grid gap-3 sm:grid-cols-2">
              {catalog.plans.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setPlanId(p.id)}
                  className={cn(
                    "rounded-xl border p-4 text-left transition",
                    p.id === planId ? "border-phosphor/70 bg-primary/5" : "border-border hover:border-border"
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{p.name}</span>
                    {overview?.plan.id === p.id && (
                      <span className=" text-[11px] uppercase text-cyan-signal">current</span>
                    )}
                  </div>
                  <p className="mt-1 font-mono text-xs text-muted-foreground">
                    {formatMoney(p.monthly_price, catalog.currency)}/mo{p.per_client ? " per client" : ""}
                  </p>
                </button>
              ))}
            </div>

            <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
              <span className="text-sm text-muted-foreground">Billing term</span>
              <IntervalToggle catalog={catalog} value={interval} onChange={setBillingInterval} />
            </div>

            {plan?.per_client && (
              <div className="mt-4 flex items-center justify-between gap-3">
                <span className="text-sm text-muted-foreground">
                  Client organizations <span className="opacity-60">(min {plan.min_quantity})</span>
                </span>
                <ClientStepper value={qty} min={plan.min_quantity} max={MAX_CLIENTS} onChange={setClients} />
              </div>
            )}

            <div className="mt-4 flex items-center justify-between gap-3">
              <span className="text-sm text-muted-foreground">
                Extra root domains{" "}
                <span className="opacity-60">
                  ({formatMoney(catalog.addons.extra_domain.monthly_price, catalog.currency)}/mo each)
                </span>
              </span>
              <ClientStepper
                value={extraDomains}
                min={0}
                max={MAX_EXTRA_DOMAINS}
                label="extra root domains"
                onChange={setExtraDomains}
              />
            </div>
          </SectionCard>

          <SectionCard title="Payment" icon={<CreditCard className="h-4 w-4" />}>
            {hasAutoRenew && payment === "subscription" ? (
              <p className="text-sm text-muted-foreground">
                You already have an auto-renewing plan. Confirming switches it now; the
                difference for the rest of this term is charged or credited to your saved
                payment method.
              </p>
            ) : null}
            <div className="mt-2 grid gap-3">
              {catalog.payment_options.map((o) => (
                <label
                  key={o.id}
                  className={cn(
                    "flex cursor-pointer gap-3 rounded-xl border p-4 transition",
                    payment === o.id ? "border-phosphor/70 bg-primary/5" : "border-border hover:border-border"
                  )}
                >
                  <input
                    type="radio"
                    name="payment"
                    className="mt-1 accent-[hsl(var(--primary))]"
                    checked={payment === o.id}
                    onChange={() => setPayment(o.id)}
                  />
                  <div>
                    <div className="flex items-center gap-2 font-medium">
                      {o.id === "subscription" ? <CreditCard className="h-4 w-4" /> : <Landmark className="h-4 w-4" />}
                      {o.label}
                    </div>
                    <p className="mt-0.5 text-sm text-muted-foreground">{o.description}</p>
                    <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                      {o.methods.map((m) => METHOD_LABELS[m] ?? m).join(" · ")}
                    </p>
                  </div>
                </label>
              ))}
            </div>
          </SectionCard>
        </div>

        <div>
          <SectionCard title="Order summary" accent="brand" className="lg:sticky lg:top-6">
            {plan && (
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt>{plan.name}{plan.per_client ? ` × ${qty} clients` : ""}</dt>
                  <dd className="font-mono">
                    {formatMoney((plan.prices[interval] ?? 0) * qty, catalog.currency)}
                  </dd>
                </div>
                {extraDomains > 0 && (
                  <div className="flex justify-between">
                    <dt>Extra root domains × {extraDomains}</dt>
                    <dd className="font-mono">
                      {formatMoney((catalog.addons.extra_domain.prices[interval] ?? 0) * extraDomains, catalog.currency)}
                    </dd>
                  </div>
                )}
                <div className="flex justify-between border-t border-border pt-2 text-base font-semibold">
                  <dt>Total per {months === 12 ? "year" : "quarter"}</dt>
                  <dd className="font-mono">{formatMoney(quote?.total, catalog.currency)}</dd>
                </div>
                <p className="text-[11px] text-muted-foreground">
                  Taxes, if any, are calculated by Stripe. Promotion codes can be entered on the next page.
                </p>
                {quote && (
                  <div className="mt-3 rounded-lg border border-border p-3 text-xs text-muted-foreground">
                    Includes {quote.limits.root_domains ?? "unlimited"} root domains,{" "}
                    {quote.limits.hosts?.toLocaleString() ?? "unlimited"} hosts,{" "}
                    {quote.limits.users ?? "unlimited"} users and{" "}
                    {quote.limits.scans_per_month?.toLocaleString() ?? "unlimited"} scans a month, with{" "}
                    {plan.scan_frequency} scheduled scans.
                  </div>
                )}
                {quoteError && (
                  <p className="mt-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
                    {quoteError}
                  </p>
                )}
              </dl>
            )}

            {conflicts.length > 0 && !sameAsCurrent && (
              <div className="mt-4 rounded-lg border border-amber-500/40 bg-amber-500/[0.08] p-3 text-xs">
                <p className="flex items-center gap-1.5 font-medium text-foreground">
                  <AlertTriangle className="h-3.5 w-3.5 text-amber-400" /> You use more than this plan allows
                </p>
                <ul className="mt-1.5 space-y-0.5 text-muted-foreground">
                  {conflicts.map((c) => (
                    <li key={c.metric}>
                      {LIMIT_LABELS[c.metric]}: {c.used.toLocaleString()} in use, plan allows {c.limit.toLocaleString()}
                    </li>
                  ))}
                </ul>
                <p className="mt-1.5 text-muted-foreground">
                  {conflicts.some((c) => c.metric === "root_domains")
                    ? "Your oldest root domains up to the new allowance keep scanning and the rest are paused. Adding extra root domains above avoids this. "
                    : ""}
                  {conflicts.some((c) => c.metric === "users") ? "No new members can be invited until you are under the seat limit. " : ""}
                  Nothing is deleted.
                </p>
                <label className="mt-2 flex cursor-pointer items-start gap-2 text-foreground">
                  <input
                    type="checkbox"
                    className="mt-0.5 accent-[hsl(var(--primary))]"
                    checked={acceptOver}
                    onChange={(e) => setAcceptOver(e.target.checked)}
                  />
                  I understand, continue with this plan
                </label>
              </div>
            )}
            {prepaidSwitch && (
              <p className="mt-4 flex gap-2 rounded-lg border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
                <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                Your prepaid {overview!.plan.name} term ends {overview!.current_period_end ? new Date(overview!.current_period_end).toLocaleDateString() : "soon"}.
                Paying for {plan!.name} now starts a new term today and the unused days are not refunded automatically.
                Contact us if you want them credited.
              </p>
            )}
            {prepaidRenewal && (
              <p className="mt-4 text-xs text-muted-foreground">
                The new term starts when your current one ends, so no days are lost.
              </p>
            )}
            {managed && (
              <p className="mt-4 text-sm text-muted-foreground">
                Your plan is managed by CAZO and invoiced directly. Contact us to change it.
              </p>
            )}
            {error && <p className="mt-4 text-sm text-destructive">{error}</p>}
            {!canManage && (
              <p className="mt-4 text-sm text-muted-foreground">
                Only an organization owner or admin can change the plan.
              </p>
            )}

            <Button
              className="mt-5 w-full"
              size="lg"
              disabled={
                !plan ||
                !quote ||
                submitting ||
                !catalog.checkout_enabled ||
                !canManage ||
                !user?.organization_id ||
                managed ||
                sameAsCurrent ||
                (conflicts.length > 0 && !acceptOver)
              }
              onClick={submit}
            >
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Lock className="h-4 w-4" />}
              {sameAsCurrent
                ? "This is your current plan"
                : hasAutoRenew && payment === "subscription"
                  ? "Switch plan"
                  : "Continue to secure payment"}
            </Button>
            <p className="mt-3 text-center text-[11px] text-muted-foreground">
              {selectedOption?.id === "prepaid"
                ? "One payment for the whole term. It does not renew automatically."
                : "Renews automatically. Cancel any time before the next term."}
            </p>
          </SectionCard>
        </div>
      </div>
    </div>
  );
}

export default function CheckoutPage() {
  return (
    <ProtectedRoute>
      <Suspense fallback={null}>
        <CheckoutInner />
      </Suspense>
    </ProtectedRoute>
  );
}
