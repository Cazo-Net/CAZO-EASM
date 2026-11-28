"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Check, ChevronDown, CreditCard, FileSearch, Globe, Loader2, Radar, ShieldCheck } from "lucide-react";
import { LandingNav, LandingFooter } from "@/components/marketing/LandingSections";
import { IntervalToggle, PlanCard } from "@/components/billing/PlanGrid";
import { useAuth } from "@/contexts/AuthContext";
import {
  formatMoney,
  getBillingOverview,
  getPlans,
  METHOD_LABELS,
  type BillingInterval,
  type PlanCatalog,
  type PlanInfo,
} from "@/lib/api-billing";

const FAQ = [
  {
    q: "What counts as a root domain?",
    a: "A registrable domain such as example.com or example.com.my. All of its subdomains are included, up to your plan's host allowance.",
  },
  {
    q: "Can I add more domains without upgrading?",
    a: "Yes. Extra root domains can be added to any plan at checkout.",
  },
  {
    q: "How can I pay?",
    a: "By card, renewing automatically each term, or as a single payment for one term. Local methods such as FPX are offered for one-term payments where available. Annual contracts paid by bank transfer are also possible; contact us.",
  },
  {
    q: "Do you offer a trial?",
    a: "Every new organization can scan one root domain for free. Contact us for a full exposure report before you buy.",
  },
];

const INCLUDED = [
  { icon: Radar, title: "Continuous discovery", body: "Subdomains, ports, certificates and services." },
  { icon: ShieldCheck, title: "Risk scoring", body: "Findings ranked so the urgent ones come first." },
  { icon: FileSearch, title: "CVE matching", body: "Detected software checked against known CVEs." },
  { icon: Globe, title: "Nothing to install", body: "Scans run from the outside, like an attacker." },
];

const num = (v: number | null, perClient = false) =>
  v == null ? "Unlimited" : `${v.toLocaleString()}${perClient ? " per client" : ""}`;

const COMPARE_ROWS: { label: string; value: (p: PlanInfo) => string }[] = [
  { label: "Root domains", value: (p) => num(p.limits.root_domains, p.per_client) },
  { label: "Hosts monitored", value: (p) => num(p.limits.hosts, p.per_client) },
  { label: "Scans per month", value: (p) => num(p.limits.scans_per_month, p.per_client) },
  { label: "User seats", value: (p) => num(p.limits.users) },
  {
    label: "Scheduled scans",
    value: (p) => p.scan_frequency.charAt(0).toUpperCase() + p.scan_frequency.slice(1),
  },
];

export default function PricingPage() {
  const { isAuthenticated } = useAuth();
  const [catalog, setCatalog] = useState<PlanCatalog | null>(null);
  const [error, setError] = useState("");
  const [interval, setBillingInterval] = useState<BillingInterval>("year");
  const [clients, setClients] = useState(10);
  const [currentPlan, setCurrentPlan] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated) return;
    getBillingOverview()
      .then((o) => setCurrentPlan(["active", "trialing", "past_due"].includes(o.status) ? o.plan.id : null))
      .catch(() => undefined);
  }, [isAuthenticated]);

  useEffect(() => {
    getPlans()
      .then(setCatalog)
      .catch(() => setError("Pricing could not be loaded. Please try again shortly."));
  }, []);

  const checkoutHref = (planId: string) => {
    const params = new URLSearchParams({ plan: planId, interval });
    if (planId === "mssp") params.set("clients", String(clients));
    // Visitors sign up first (registration ends in onboarding, where the
    // organization is created); they can then pick the plan from Billing.
    return isAuthenticated ? `/billing/checkout?${params.toString()}` : "/register";
  };

  const methods = Array.from(new Set(catalog?.payment_options.flatMap((o) => o.methods) ?? []));
  const salesHref = `mailto:${process.env.NEXT_PUBLIC_SALES_EMAIL || "sales@cazoeasm.io"}?subject=CAZO%20EASM%20pricing`;

  return (
    <div className="h-screen overflow-y-auto bg-void text-foreground">
      <LandingNav scrolled />

      <section className="relative overflow-hidden">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-0 h-[420px] bg-[radial-gradient(60%_100%_at_50%_0%,hsl(var(--primary)/0.16),transparent_70%)]"
        />
        <div className="relative mx-auto max-w-6xl px-6 pb-10 pt-16 text-center md:pt-20">
          <span className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">Pricing</span>
          <h1 className="mx-auto mt-4 max-w-3xl text-4xl font-semibold leading-[1.08] tracking-tight md:text-5xl">
            Priced by root domain. No surprise bills.
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-muted-foreground">
            Pick the number of domains you need and add more any time. Your first root
            domain is free to scan, with no card.
          </p>
          {catalog && (
            <div className="mt-8 flex justify-center">
              <IntervalToggle catalog={catalog} value={interval} onChange={setBillingInterval} />
            </div>
          )}
          {catalog?.test_mode && (
            <p className="mt-4 font-mono text-[11px] text-amber-400">
              Test mode: no real payments are taken.
            </p>
          )}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-16">
        {error && <p className="text-center text-sm text-destructive">{error}</p>}
        {!catalog && !error && (
          <div className="flex justify-center py-20">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}
        {catalog && (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            {catalog.plans.map((plan) => (
              <PlanCard
                key={plan.id}
                plan={plan}
                catalog={catalog}
                interval={interval}
                clients={clients}
                onClientsChange={setClients}
                current={currentPlan === plan.id}
                cta={
                  <Link
                    href={checkoutHref(plan.id)}
                    className={
                      plan.highlight
                        ? "inline-flex w-full items-center justify-center gap-2 rounded-md bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                        : "inline-flex w-full items-center justify-center gap-2 rounded-md border border-input bg-background/40 px-4 py-2.5 text-sm font-medium transition hover:border-primary/60"
                    }
                  >
                    {currentPlan === plan.id ? "Manage plan" : `Choose ${plan.name}`} <ArrowRight className="h-4 w-4" />
                  </Link>
                }
              />
            ))}
          </div>
        )}

        {/* Free first scan */}
        <div className="mt-5 flex flex-col items-start justify-between gap-4 rounded-xl border border-dashed border-border p-6 md:flex-row md:items-center">
          <div>
            <p className="font-medium">Not ready to pick a plan?</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Create an account and scan one root domain you own for free. Upgrade when you
              need more.
            </p>
          </div>
          <Link
            href="/register"
            className="inline-flex shrink-0 items-center gap-2 rounded-md border border-input bg-card px-4 py-2 text-sm font-medium transition hover:border-primary/60"
          >
            Start free scan <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>

      {/* Included in every plan */}
      <section className="border-y border-border/60 bg-card/40">
        <div className="mx-auto max-w-6xl px-6 py-14">
          <h2 className="text-2xl font-semibold tracking-tight">In every plan</h2>
          <div className="mt-8 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {INCLUDED.map(({ icon: Icon, title, body }) => (
              <div key={title}>
                <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-card text-primary">
                  <Icon className="h-4 w-4" />
                </span>
                <p className="mt-4 font-medium">{title}</p>
                <p className="mt-1 text-sm text-muted-foreground">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Compare */}
      {catalog && (
        <section className="mx-auto max-w-6xl px-6 py-16">
          <h2 className="text-2xl font-semibold tracking-tight">Compare plans</h2>
          <div className="mt-6 overflow-x-auto rounded-xl border border-border">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="border-b border-border bg-card">
                  <th scope="col" className="px-5 py-4 font-medium text-muted-foreground">
                    Limits
                  </th>
                  {catalog.plans.map((p) => (
                    <th key={p.id} scope="col" className="px-5 py-4">
                      <span className={p.highlight ? "font-semibold text-primary" : "font-semibold"}>
                        {p.name}
                      </span>
                      <span className="mt-0.5 block text-xs font-normal text-muted-foreground">
                        {formatMoney(p.monthly_price, catalog.currency)} / month
                        {p.per_client ? " per client" : ""}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {COMPARE_ROWS.map((row) => (
                  <tr key={row.label} className="border-b border-border/60 last:border-0">
                    <th scope="row" className="px-5 py-3.5 font-normal text-muted-foreground">
                      {row.label}
                    </th>
                    {catalog.plans.map((p) => (
                      <td key={p.id} className="px-5 py-3.5 tabular-nums">
                        {row.value(p)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-5 grid gap-5 md:grid-cols-3">
            <div className="rounded-xl border border-border bg-card p-5 text-sm">
              <Globe className="h-4 w-4 text-primary" />
              <p className="mt-3 font-medium">Extra root domains</p>
              <p className="mt-1 text-muted-foreground">
                {formatMoney(catalog.addons.extra_domain.monthly_price, catalog.currency)} per domain
                per month on any plan, added at checkout.
              </p>
            </div>
            <div className="rounded-xl border border-border bg-card p-5 text-sm">
              <CreditCard className="h-4 w-4 text-primary" />
              <p className="mt-3 font-medium">Payment methods</p>
              <p className="mt-1 text-muted-foreground">
                {methods.map((m) => METHOD_LABELS[m] ?? m).join(", ")}. Payments are processed
                securely by Stripe; card details never touch our servers.
              </p>
            </div>
            <div className="flex flex-col rounded-xl border border-border bg-card p-5 text-sm">
              <Check className="h-4 w-4 text-primary" />
              <p className="mt-3 font-medium">Contracts and invoices</p>
              <p className="mt-1 text-muted-foreground">
                Annual contracts, bank transfer and local-currency invoices are set up directly.
              </p>
              <a href={salesHref} className="mt-3 inline-flex items-center gap-1.5 font-medium text-primary hover:underline">
                Contact sales <ArrowRight className="h-3.5 w-3.5" />
              </a>
            </div>
          </div>
        </section>
      )}

      <section className="mx-auto max-w-3xl px-6 pb-20">
        <h2 className="text-2xl font-semibold tracking-tight">Questions</h2>
        <div className="mt-6 divide-y divide-border rounded-xl border border-border bg-card">
          {FAQ.map((f, i) => (
            <details key={f.q} className="group px-5" open={i === 0}>
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4 font-medium [&::-webkit-details-marker]:hidden">
                {f.q}
                <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
              </summary>
              <p className="pb-5 text-sm leading-relaxed text-muted-foreground">{f.a}</p>
            </details>
          ))}
        </div>
      </section>

      <LandingFooter />
    </div>
  );
}
