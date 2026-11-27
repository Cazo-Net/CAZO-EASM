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
      className="inline-flex rounded-xl border border-border/60 bg-card/40 p-1"
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
              ? "bg-phosphor text-void shadow-glow-sm"
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
  onChange,
}: {
  value: number;
  min: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        aria-label="Fewer clients"
        onClick={() => onChange(Math.max(min, value - 1))}
        disabled={value <= min}
        className="flex h-8 w-8 items-center justify-center rounded-lg border border-border/60 text-muted-foreground transition hover:text-foreground disabled:opacity-40"
      >
        <Minus className="h-3.5 w-3.5" />
      </button>
      <input
        type="number"
        min={min}
        value={value}
        aria-label="Number of clients"
        onChange={(e) => onChange(Math.max(min, Number(e.target.value) || min))}
        className="h-8 w-16 rounded-lg border border-border/60 bg-transparent text-center font-mono text-sm"
      />
      <button
        type="button"
        aria-label="More clients"
        onClick={() => onChange(value + 1)}
        className="flex h-8 w-8 items-center justify-center rounded-lg border border-border/60 text-muted-foreground transition hover:text-foreground"
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

  return (
    <div
      className={cn(
        "relative flex flex-col rounded-2xl border bg-card/50 p-6 backdrop-blur-sm",
        plan.highlight ? "border-phosphor/60 shadow-glow-sm" : "border-border/50"
      )}
    >
      {plan.highlight && (
        <span className="absolute -top-3 left-6 rounded-full bg-phosphor px-3 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-widest text-void">
          Most popular
        </span>
      )}
      {current && (
        <span className="absolute -top-3 right-6 rounded-full border border-cyan-signal/60 bg-void px-3 py-0.5 font-mono text-[10px] uppercase tracking-widest text-cyan-signal">
          Current plan
        </span>
      )}
      <h3 className="font-display text-xl font-semibold">{plan.name}</h3>
      <p className="mt-1 min-h-[40px] text-sm text-muted-foreground">{plan.tagline}</p>

      <div className="mt-5">
        <div className="flex items-baseline gap-1.5">
          <span className="font-display text-4xl font-semibold">
            {formatMoney(plan.monthly_price, catalog.currency)}
          </span>
          <span className="text-sm text-muted-foreground">
            /month{plan.per_client ? " per client" : ""}
          </span>
        </div>
        <p className="mt-1 font-mono text-[11px] text-muted-foreground">
          {formatMoney(term, catalog.currency)} billed every {months === 12 ? "year" : `${months} months`}
          {plan.per_client ? ` for ${qty} clients` : ""}
        </p>
      </div>

      {plan.per_client && (
        <div className="mt-4 flex items-center justify-between gap-3 rounded-xl border border-border/40 p-3">
          <span className="text-xs text-muted-foreground">
            Clients <span className="opacity-60">(min {plan.min_quantity})</span>
          </span>
          <ClientStepper value={qty} min={plan.min_quantity} onChange={onClientsChange} />
        </div>
      )}

      <ul className="mt-5 space-y-2 text-sm">
        <li className="flex gap-2">
          <Check className="mt-0.5 h-4 w-4 shrink-0 text-phosphor" />
          {limitText(plan.limits.root_domains, "root domains", plan.per_client)}
        </li>
        <li className="flex gap-2">
          <Check className="mt-0.5 h-4 w-4 shrink-0 text-phosphor" />
          {limitText(plan.limits.hosts, "hosts monitored", plan.per_client)}
        </li>
        <li className="flex gap-2">
          <Check className="mt-0.5 h-4 w-4 shrink-0 text-phosphor" />
          <span>
            <span className="capitalize">{plan.scan_frequency}</span> scheduled scans
          </span>
        </li>
        <li className="flex gap-2">
          <Check className="mt-0.5 h-4 w-4 shrink-0 text-phosphor" />
          {plan.limits.users == null ? "Unlimited users" : `${plan.limits.users} user seats`}
        </li>
        {plan.features.map((f) => (
          <li key={f} className="flex gap-2">
            <Check className="mt-0.5 h-4 w-4 shrink-0 text-phosphor" />
            {f}
          </li>
        ))}
      </ul>

      <div className="mt-auto pt-6">{cta}</div>
    </div>
  );
}
