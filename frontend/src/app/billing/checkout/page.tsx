"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, CreditCard, Landmark, Loader2, Lock, ShieldCheck } from "lucide-react";
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
  METHOD_LABELS,
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
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const canceled = params.get("canceled") === "1";

  const canManage = user?.role === "owner" || user?.role === "admin";

  useEffect(() => {
    Promise.all([getPlans(), getBillingOverview().catch(() => null)])
      .then(([c, o]) => {
        setCatalog(c);
        setOverview(o);
      })
      .catch(() => setError("Could not load plans."));
  }, []);

  const plan = useMemo(() => catalog?.plans.find((p) => p.id === planId) ?? null, [catalog, planId]);

  useEffect(() => {
    if (!plan) return;
    let cancelled = false;
    getQuote({ plan: plan.id, interval, clients, extra_domains: extraDomains })
      .then((q) => !cancelled && setQuote(q))
      .catch(() => !cancelled && setQuote(null));
    return () => {
      cancelled = true;
    };
  }, [plan, interval, clients, extraDomains]);

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
        clients,
        extra_domains: extraDomains,
        payment,
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
        {error ? <p className="text-sm text-red-400">{error}</p> : <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />}
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
        <div className="mb-4 rounded-xl border border-border/60 bg-card/40 p-3 text-sm text-muted-foreground">
          Online payment is not switched on yet. Contact sales to start a plan.
        </div>
      )}
      {!user?.organization_id && (
        <div className="mb-4 rounded-xl border border-border/60 bg-card/40 p-3 text-sm">
          Create your organization first in{" "}
          <Link className="text-phosphor underline" href="/settings/organization">Organization settings</Link>.
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
                    p.id === planId ? "border-phosphor/70 bg-phosphor/5" : "border-border/50 hover:border-border"
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{p.name}</span>
                    {overview?.plan.id === p.id && (
                      <span className="font-mono text-[10px] uppercase text-cyan-signal">current</span>
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
                <ClientStepper value={Math.max(clients, plan.min_quantity)} min={plan.min_quantity} onChange={setClients} />
              </div>
            )}

            <div className="mt-4 flex items-center justify-between gap-3">
              <span className="text-sm text-muted-foreground">
                Extra root domains{" "}
                <span className="opacity-60">
                  ({formatMoney(catalog.addons.extra_domain.monthly_price, catalog.currency)}/mo each)
                </span>
              </span>
              <ClientStepper value={extraDomains} min={0} onChange={setExtraDomains} />
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
                    payment === o.id ? "border-phosphor/70 bg-phosphor/5" : "border-border/50 hover:border-border"
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
                  <dt>{plan.name}{plan.per_client ? ` × ${quote?.clients ?? clients} clients` : ""}</dt>
                  <dd className="font-mono">
                    {formatMoney((plan.prices[interval] ?? 0) * (plan.per_client ? quote?.clients ?? clients : 1), catalog.currency)}
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
                <div className="flex justify-between border-t border-border/40 pt-2 text-base font-semibold">
                  <dt>Total per {months === 12 ? "year" : "quarter"}</dt>
                  <dd className="font-mono">{formatMoney(quote?.total, catalog.currency)}</dd>
                </div>
                <p className="text-[11px] text-muted-foreground">
                  Taxes, if any, are calculated by Stripe. Promotion codes can be entered on the next page.
                </p>
                {quote && (
                  <div className="mt-3 rounded-lg border border-border/40 p-3 text-xs text-muted-foreground">
                    Includes {quote.limits.root_domains ?? "unlimited"} root domains,{" "}
                    {quote.limits.hosts?.toLocaleString() ?? "unlimited"} hosts,{" "}
                    {quote.limits.users ?? "unlimited"} users and{" "}
                    {quote.limits.scans_per_month?.toLocaleString() ?? "unlimited"} scans a month.
                  </div>
                )}
              </dl>
            )}

            {error && <p className="mt-4 text-sm text-red-400">{error}</p>}
            {!canManage && (
              <p className="mt-4 text-sm text-muted-foreground">
                Only an organization owner or admin can change the plan.
              </p>
            )}

            <Button
              className="mt-5 w-full"
              size="lg"
              disabled={!plan || !quote || submitting || !catalog.checkout_enabled || !canManage || !user?.organization_id}
              onClick={submit}
            >
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Lock className="h-4 w-4" />}
              {hasAutoRenew && payment === "subscription" ? "Switch plan" : "Continue to secure payment"}
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
