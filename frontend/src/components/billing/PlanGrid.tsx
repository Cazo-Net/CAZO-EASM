"use client";

import { Check, Minus, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  formatMoney,
  type BillingInterval,
  type PlanCatalog,
  type PlanInfo,
} from "@/lib/api-billing";

function limitText(value: number | null, unit: string, perClient: boolean) {
  if (value == null) return `Unlimited ${unit}`;
  return `${value.toLocaleString()} ${unit}${perClient ? " per client" : ""}`;
}

export function IntervalToggle({
  catalog,
  value,
  onChange,
}: {
  catalog: PlanCatalog;
  value: BillingInterval;
  onChange: (v: BillingInterval) => void;
}) {
  return (
    <div
      role="radiogroup"
      aria-label="Billing interval"
      className="inline-flex rounded-xl border border-border bg-card p-1"
    >
      {catalog.intervals.map((i) => (
        <button
          key={i.id}
          role="radio"
          aria-checked={value === i.id}
          onClick={() => onChange(i.id)}
          className={cn(
            "rounded-lg px-4 py-1.5 text-sm font-medium transition-colors",
            value === i.id
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {i.label}
        </button>
      ))}
    </div>
  );
}

export function ClientStepper({
  value,
  min,
  max = Number.MAX_SAFE_INTEGER,
  label = "clients",
  onChange,
}: {
  value: number;
  min: number;
  max?: number;
  /** What is being counted, for screen readers ("clients", "extra root domains"). */
  label?: string;
  onChange: (v: number) => void;
}) {
  const clamp = (v: number) => Math.min(max, Math.max(min, Math.floor(v)));
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        aria-label={`Fewer ${label}`}
        onClick={() => onChange(clamp(value - 1))}
        disabled={value <= min}
        className="flex h-8 w-8 items-center justify-center rounded-lg border border-border text-muted-foreground transition hover:text-foreground disabled:opacity-40"
      >
        <Minus className="h-3.5 w-3.5" />
      </button>
      <input
        type="number"
        min={min}
        max={max === Number.MAX_SAFE_INTEGER ? undefined : max}
        value={value}
        aria-label={`Number of ${label}`}
        onChange={(e) => onChange(clamp(Number(e.target.value) || min))}
        className="h-8 w-16 rounded-lg border border-border bg-transparent text-center font-mono text-sm"
      />
      <button
        type="button"
        aria-label={`More ${label}`}
        onClick={() => onChange(clamp(value + 1))}
        disabled={value >= max}
        className="disabled:opacity-40 flex h-8 w-8 items-center justify-center rounded-lg border border-border text-muted-foreground transition hover:text-foreground"
      >
        <Plus className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

export function PlanCard({
  plan,
  catalog,
  interval,
  clients,
  onClientsChange,
  current,
  cta,
}: {
  plan: PlanInfo;
  catalog: PlanCatalog;
  interval: BillingInterval;
  clients: number;
  onClientsChange: (n: number) => void;
  current?: boolean;
  cta: React.ReactNode;
}) {
  const months = catalog.intervals.find((i) => i.id === interval)?.months ?? 12;
  const qty = plan.per_client ? Math.max(clients, plan.min_quantity) : 1;
  const term = (plan.prices[interval] ?? 0) * qty;

  const limits = [
    limitText(plan.limits.root_domains, "root domains", plan.per_client),
    limitText(plan.limits.hosts, "hosts monitored", plan.per_client),
    `${plan.scan_frequency.charAt(0).toUpperCase()}${plan.scan_frequency.slice(1)} scheduled scans`,
    limitText(plan.limits.scans_per_month, "scans a month", plan.per_client),
    plan.limits.users == null ? "Unlimited users" : `${plan.limits.users} user seats`,
  ];

  return (
    <div
      className={cn(
        "relative flex flex-col rounded-xl border p-6",
        plan.highlight
          ? "border-primary/60 bg-gradient-to-b from-primary/[0.09] via-card to-card shadow-[0_0_0_1px_hsl(var(--primary)/0.15),0_24px_60px_-30px_hsl(var(--primary)/0.55)]"
          : "border-border bg-card"
      )}
    >
      <div className="flex min-h-[26px] items-center justify-between gap-2">
        <h3 className="text-lg font-semibold">{plan.name}</h3>
        {current ? (
          <span className="rounded-full border border-border px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Current plan
          </span>
        ) : plan.highlight ? (
          <span className="rounded-full bg-primary/15 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-primary">
            Most popular
          </span>
        ) : null}
      </div>
      <p className="mt-1.5 text-sm text-muted-foreground xl:min-h-[60px]">{plan.tagline}</p>

      <div className="mt-5">
        <div className="flex items-baseline gap-1.5">
          <span className="text-4xl font-semibold tracking-tight tabular-nums">
            {formatMoney(plan.monthly_price, catalog.currency)}
          </span>
          <span className="text-sm text-muted-foreground">/ month</span>
        </div>
        <p className="mt-1.5 text-xs text-muted-foreground xl:min-h-[32px]">
          {plan.per_client ? "Per client. " : ""}
          {formatMoney(term, catalog.currency)} billed every {months === 12 ? "year" : `${months} months`}
          {plan.per_client ? ` for ${qty} clients` : ""}.
        </p>
      </div>

      <div className="mt-5">{cta}</div>

      {plan.per_client && (
        <div className="mt-3 flex items-center justify-between gap-2">
          <span className="text-xs text-muted-foreground">Clients (min {plan.min_quantity})</span>
          <ClientStepper value={qty} min={plan.min_quantity} max={10_000} onChange={onClientsChange} />
        </div>
      )}

      <div className="my-6 h-px bg-border" />

      <ul className="space-y-2.5 text-sm">
        {limits.map((l) => (
          <li key={l} className="flex gap-2.5 font-medium">
            <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            {l}
          </li>
        ))}
        {plan.features.map((f) => (
          <li key={f} className="flex gap-2.5 text-muted-foreground">
            <Check className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground/60" />
            {f}
          </li>
        ))}
      </ul>
    </div>
  );
}
