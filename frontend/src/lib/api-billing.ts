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

export interface RootDomainStatus {
  domain: string;
  first_seen: string | null;
  /** False when the domain is beyond the plan allowance (paused). */
  active: boolean;
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
  managed_by_staff: boolean;
  root_domains: RootDomainStatus[];
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
  accept_over_limit?: boolean;
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

/** The HTTP 402 body the API sends when a plan allowance is used up. */
export interface PlanLimitDetail {
  code: "plan_limit_reached";
  metric: LimitKey | "scan_frequency";
  limit: number | null;
  used: number;
  plan: string;
  plan_name: string;
  message: string;
  upgrade_url: string;
}

export function planLimitFromError(err: unknown): PlanLimitDetail | null {
  const res = (err as { response?: { status?: number; data?: { detail?: unknown } } })?.response;
  const detail = res?.data?.detail as Partial<PlanLimitDetail> | undefined;
  if (detail && typeof detail === "object" && detail.code === "plan_limit_reached") {
    return detail as PlanLimitDetail;
  }
  return null;
}

export interface OverLimitConflict {
  metric: LimitKey;
  used: number;
  limit: number;
}

/** What the org already uses beyond a candidate plan's allowances. */
export function overLimitConflicts(
  usage: Record<LimitKey, UsageMeter> | undefined,
  limits: Record<LimitKey, number | null> | undefined
): OverLimitConflict[] {
  if (!usage || !limits) return [];
  const keys: LimitKey[] = ["root_domains", "users", "hosts"];
  return keys
    .filter((k) => limits[k] != null && usage[k] && usage[k].used > (limits[k] as number))
    .map((k) => ({ metric: k, used: usage[k].used, limit: limits[k] as number }));
}

// Same list as backend/app/billing/entitlements.py (_MULTI_LABEL_SUFFIXES).
const MULTI_LABEL_SUFFIXES = new Set([
  "com.my", "net.my", "org.my", "edu.my", "gov.my", "name.my", "biz.my", "mil.my",
  "co.uk", "org.uk", "ac.uk", "gov.uk",
  "com.au", "net.au", "org.au", "edu.au", "gov.au",
  "com.sg", "edu.sg", "gov.sg", "org.sg", "net.sg",
  "co.id", "or.id", "ac.id", "go.id", "web.id",
  "com.ph", "gov.ph", "edu.ph",
  "co.th", "ac.th", "go.th", "in.th", "or.th",
  "com.vn", "gov.vn", "edu.vn",
  "co.nz", "org.nz", "govt.nz",
  "co.jp", "ne.jp", "or.jp", "ac.jp", "go.jp",
  "co.in", "net.in", "org.in", "gov.in", "ac.in",
  "com.br", "com.cn", "com.hk", "com.tw", "co.kr", "co.za", "com.mx", "com.tr",
]);

/** Registrable root of a hostname, URL or wildcard (mirrors the backend; the API decides). */
export function rootDomainOf(target: string): string {
  let host = (target || "").trim().toLowerCase();
  if (host.includes("://")) host = host.split("://")[1];
  host = host.split("/")[0].split("?")[0];
  if ((host.match(/:/g) || []).length === 1) host = host.split(":")[0];
  host = host.replace(/^[*.]+/, "").replace(/\.+$/, "");
  if (/^\d{1,3}(\.\d{1,3}){3}$/.test(host)) return host;
  const labels = host.split(".").filter(Boolean);
  if (labels.length <= 2) return labels.join(".");
  if (MULTI_LABEL_SUFFIXES.has(labels.slice(-2).join("."))) return labels.slice(-3).join(".");
  return labels.slice(-2).join(".");
}

export const MAX_EXTRA_DOMAINS = 500;
export const MAX_CLIENTS = 10_000;

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
