import api from "@/lib/api";

export type BillingInterval = "year" | "quarter";
export type PaymentChoice = "subscription" | "prepaid";
export type LimitKey = "root_domains" | "hosts" | "users" | "scans_per_month";

export interface PlanInfo {
  id: string;
  name: string;
  tagline: string;
  highlight: boolean;
  per_client: boolean;
  min_quantity: number;
  monthly_price: number | null;
  prices: Record<BillingInterval, number | null>;
  limits: Record<LimitKey, number | null>;
  scan_frequency: string;
  features: string[];
}

export interface PaymentOption {
  id: PaymentChoice;
  label: string;
  description: string;
  methods: string[];
}

export interface PlanCatalog {
  currency: string;
  intervals: { id: BillingInterval; label: string; months: number }[];
  plans: PlanInfo[];
  addons: { extra_domain: { monthly_price: number | null; prices: Record<BillingInterval, number | null> } };
  payment_options: PaymentOption[];
  checkout_enabled: boolean;
  test_mode: boolean;
}

export interface UsageMeter {
  used: number;
  limit: number | null;
  unlimited: boolean;
}

export interface BillingOverview {
  organization_id: string;
  plan: PlanInfo;
  status: string;
  payment_mode: "subscription" | "prepaid" | "manual" | null;
  interval: BillingInterval | null;
  clients: number;
  extra_domains: number;
  currency: string;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  last_payment_error: string | null;
  has_customer: boolean;
  usage: Record<LimitKey, UsageMeter>;
  checkout_enabled: boolean;
  test_mode: boolean;
}

export interface Quote {
  plan: string;
  interval: BillingInterval;
  clients: number;
  extra_domains: number;
  currency: string;
  total: number;
  limits: Record<LimitKey, number | null>;
}

export interface PaymentMethod {
  id: string;
  type: string;
  brand: string;
  last4: string | null;
  exp_month: number | null;
  exp_year: number | null;
  is_default: boolean;
}

export interface Invoice {
  id: string;
  number: string | null;
  description: string | null;
  amount: number;
  currency: string;
  status: string;
  hosted_url: string | null;
  pdf_url: string | null;
  period_start: string | null;
  period_end: string | null;
  paid_at: string | null;
  created_at: string;
}

export interface CheckoutOrder {
  plan: string;
  interval: BillingInterval;
  clients?: number;
  extra_domains?: number;
  payment: PaymentChoice;
}

export async function getPlans(): Promise<PlanCatalog> {
  const { data } = await api.get("/billing/plans");
  return data;
}

export async function getQuote(order: Omit<CheckoutOrder, "payment">): Promise<Quote> {
  const { data } = await api.post("/billing/quote", order);
  return data;
}

export async function getBillingOverview(): Promise<BillingOverview> {
  const { data } = await api.get("/billing/subscription");
  return data;
}

export async function startCheckout(order: CheckoutOrder): Promise<{ url: string | null; updated: boolean }> {
  const { data } = await api.post("/billing/checkout", order);
  return data;
}

export async function getCheckoutStatus(sessionId: string) {
  const { data } = await api.get(`/billing/checkout/${encodeURIComponent(sessionId)}`);
  return data as {
    status: string;
    payment_status: string;
    mode: string;
    amount_total: number | null;
    currency: string | null;
    plan: string | null;
  };
}

export async function openBillingPortal(): Promise<string> {
  const { data } = await api.post("/billing/portal");
  return data.url;
}

export async function listPaymentMethods(): Promise<PaymentMethod[]> {
  const { data } = await api.get("/billing/payment-methods");
  return data.payment_methods;
}

export async function addPaymentMethod(): Promise<string> {
  const { data } = await api.post("/billing/payment-methods/setup");
  return data.url;
}

export async function setDefaultPaymentMethod(id: string) {
  await api.post(`/billing/payment-methods/${encodeURIComponent(id)}/default`);
}

export async function removePaymentMethod(id: string) {
  await api.delete(`/billing/payment-methods/${encodeURIComponent(id)}`);
}

export async function listInvoices(): Promise<Invoice[]> {
  const { data } = await api.get("/billing/invoices");
  return data.invoices;
}

export async function cancelPlan() {
  const { data } = await api.post("/billing/cancel", { at_period_end: true });
  return data;
}

export async function resumePlan() {
  const { data } = await api.post("/billing/resume");
  return data;
}

export function formatMoney(amount: number | null | undefined, currency: string): string {
  if (amount == null) return "—";
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: currency.toUpperCase(),
      maximumFractionDigits: amount % 100 === 0 ? 0 : 2,
    }).format(amount / 100);
  } catch {
    return `${currency.toUpperCase()} ${(amount / 100).toFixed(2)}`;
  }
}

/** Pull a readable message out of an API error (handles the 402 plan-limit shape). */
export function billingErrorMessage(err: unknown, fallback = "Something went wrong."): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (!detail) return fallback;
  if (typeof detail === "string") return detail;
  if (typeof detail === "object" && detail && "message" in detail) {
    return String((detail as { message: unknown }).message);
  }
  return fallback;
}

export const LIMIT_LABELS: Record<LimitKey, string> = {
  root_domains: "Root domains",
  hosts: "Hosts monitored",
  users: "User seats",
  scans_per_month: "Scans this month",
};

export const METHOD_LABELS: Record<string, string> = {
  card: "Cards",
  fpx: "FPX online banking",
  grabpay: "GrabPay",
};
