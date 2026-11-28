"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Building2, Loader2 } from "lucide-react";
import { LandingNav, LandingFooter } from "@/components/marketing/LandingSections";
import { IntervalToggle, PlanCard } from "@/components/billing/PlanGrid";
import { useAuth } from "@/contexts/AuthContext";
import {
  formatMoney,
  getPlans,
  METHOD_LABELS,
  type BillingInterval,
  type PlanCatalog,
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

export default function PricingPage() {
  const { isAuthenticated } = useAuth();
  const [catalog, setCatalog] = useState<PlanCatalog | null>(null);
  const [error, setError] = useState("");
  const [interval, setBillingInterval] = useState<BillingInterval>("year");
  const [clients, setClients] = useState(10);

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

  return (
    <div className="h-screen overflow-y-auto bg-void text-foreground">
      <LandingNav scrolled />

      <section className="mx-auto max-w-6xl px-6 pb-10 pt-16 text-center">
        <span className=" text-[11px] uppercase tracking-wide text-phosphor">Pricing</span>
        <h1 className="mt-4 text-4xl font-semibold leading-[1.05] md:text-5xl">
          Priced by root domain. No surprise bills.
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-muted-foreground">
          Every plan includes continuous discovery, risk scoring and CVE matching. Pick the
          number of domains you need and add more any time.
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
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-16">
        {error && <p className="text-center text-sm text-red-400">{error}</p>}
        {!catalog && !error && (
          <div className="flex justify-center py-20">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}
        {catalog && (
          <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
            {catalog.plans.map((plan) => (
              <PlanCard
                key={plan.id}
                plan={plan}
                catalog={catalog}
                interval={interval}
                clients={clients}
                onClientsChange={setClients}
                cta={
                  <Link
                    href={checkoutHref(plan.id)}
                    className={
                      plan.highlight
                        ? "inline-flex w-full items-center justify-center gap-2 rounded-xl bg-phosphor px-4 py-2.5 text-sm font-semibold text-void transition hover:"
                        : "inline-flex w-full items-center justify-center gap-2 rounded-xl border border-border px-4 py-2.5 text-sm font-medium transition hover:border-phosphor/60"
                    }
                  >
                    Choose {plan.name} <ArrowRight className="h-4 w-4" />
                  </Link>
                }
              />
            ))}
          </div>
        )}

        {catalog && (
          <div className="mt-8 grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-border bg-card p-5 text-sm">
              <p className="font-medium">Extra root domains</p>
              <p className="mt-1 text-muted-foreground">
                {formatMoney(catalog.addons.extra_domain.monthly_price, catalog.currency)} per domain per
                month on any plan, added at checkout.
              </p>
            </div>
            <div className="rounded-xl border border-border bg-card p-5 text-sm">
              <p className="font-medium">Payment methods</p>
              <p className="mt-1 text-muted-foreground">
                {methods.map((m) => METHOD_LABELS[m] ?? m).join(", ")}. Payments are processed
                securely by Stripe; card details never touch our servers.
              </p>
            </div>
          </div>
        )}

        <div className="mt-8 flex flex-col items-start justify-between gap-4 rounded-xl border border-border bg-card p-6 md:flex-row md:items-center">
          <div className="flex gap-3">
            <Building2 className="mt-0.5 h-5 w-5 text-cyan-signal" />
            <div>
              <p className="font-medium">Need an annual contract, bank transfer or a local-currency invoice?</p>
              <p className="text-sm text-muted-foreground">
                We set up contracts and design-partner pricing directly.
              </p>
            </div>
          </div>
          <a
            href={`mailto:${process.env.NEXT_PUBLIC_SALES_EMAIL || "sales@cazo.io"}?subject=CAZO%20EASM%20pricing`}
            className="inline-flex items-center gap-2 rounded-xl border border-border px-4 py-2 text-sm font-medium transition hover:border-phosphor/60"
          >
            Contact sales
          </a>
        </div>
      </section>

      <section className="mx-auto max-w-3xl px-6 pb-20">
        <h2 className="text-2xl font-semibold">Questions</h2>
        <dl className="mt-6 space-y-5">
          {FAQ.map((f) => (
            <div key={f.q}>
              <dt className="font-medium">{f.q}</dt>
              <dd className="mt-1 text-sm text-muted-foreground">{f.a}</dd>
            </div>
          ))}
        </dl>
      </section>

      <LandingFooter />
    </div>
  );
}
