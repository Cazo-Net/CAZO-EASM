"use client";

import { useEffect, useState, useCallback } from "react";
import { CreditCard, Receipt, RefreshCw, ExternalLink, AlertTriangle, ArrowLeft } from "lucide-react";
import api, {
  listPlans,
  getSubscription,
  createCheckoutSession,
  getBillingPortal,
  upgradePlan,
  cancelSubscription,
  resumeSubscription,
  startTrial,
  listInvoices,
  listPaymentMethods,
  removePaymentMethod,
  setDefaultPaymentMethod,
  getUsageSummary,
  refreshUsage,
} from "@/lib/api";
import { PageHeader } from "@/components/common/PageHeader";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PlanCard } from "@/components/billing/PlanCard";
import { SubscriptionStatus } from "@/components/billing/SubscriptionStatus";
import { InvoiceList } from "@/components/billing/InvoiceList";
import { PaymentMethodList } from "@/components/billing/PaymentMethods";
import { UsageCard } from "@/components/billing/UsageMeter";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { Plan, Subscription, Invoice, PaymentMethod, UsageSummary } from "@/types";

function BillingContent() {
  const { user } = useAuth();
  const router = useRouter();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethod[]>([]);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [plansRes, subRes, invoicesRes, pmRes, usageRes] = await Promise.allSettled([
        listPlans(),
        getSubscription(),
        listInvoices(),
        listPaymentMethods(),
        getUsageSummary(),
      ]);

      if (plansRes.status === "fulfilled") setPlans(plansRes.value);
      if (subRes.status === "fulfilled") setSubscription(subRes.value);
      if (invoicesRes.status === "fulfilled") setInvoices(invoicesRes.value);
      if (pmRes.status === "fulfilled") setPaymentMethods(pmRes.value);
      if (usageRes.status === "fulfilled") setUsage(usageRes.value);
    } catch (err) {
      console.error("Failed to fetch billing data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handlePlanSelect = async (planId: string) => {
    if (planId === "enterprise") {
      window.open("mailto:sales@cazo.io?subject=Enterprise%20Plan%20Inquiry", "_blank");
      return;
    }

    setActionLoading(true);
    setError(null);
    try {
      if (subscription?.status === "trial" || !subscription) {
        await createCheckoutSession({
          plan: planId,
          success_url: `${window.location.origin}/billing?success=true`,
          cancel_url: `${window.location.origin}/billing`,
        });
      } else {
        await upgradePlan(planId);
        await fetchData();
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to process plan change");
    } finally {
      setActionLoading(false);
    }
  };

  const handleManageBilling = async () => {
    setActionLoading(true);
    try {
      const res = await getBillingPortal(window.location.href);
      if (res.url) window.location.href = res.url;
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to open billing portal");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!confirm("Are you sure you want to cancel your subscription?")) return;
    setActionLoading(true);
    try {
      await cancelSubscription(true);
      await fetchData();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to cancel subscription");
    } finally {
      setActionLoading(false);
    }
  };

  const handleResume = async () => {
    setActionLoading(true);
    try {
      await resumeSubscription();
      await fetchData();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to resume subscription");
    } finally {
      setActionLoading(false);
    }
  };

  const handleStartTrial = async () => {
    setActionLoading(true);
    setError(null);
    try {
      await startTrial();
      await fetchData();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to start trial");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRefreshUsage = async () => {
    try {
      const res = await refreshUsage();
      setUsage(res);
    } catch (err) {
      console.error("Failed to refresh usage:", err);
    }
  };

  return (
    <div className="min-h-screen">
      <PageHeader
        title="Billing & Subscription"
        description="Manage your subscription, payment methods, and invoices"
        icon={<CreditCard className="w-6 h-6" />}
        actions={
          <Button variant="outline" onClick={() => router.push("/settings")}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Settings
          </Button>
        }
      />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {error && (
          <div className="flex items-center gap-2 p-4 rounded-lg bg-destructive/10 text-destructive border border-destructive/20">
            <AlertTriangle className="w-4 h-4" />
            <p className="text-sm">{error}</p>
            <Button variant="ghost" size="sm" onClick={() => setError(null)} className="ml-auto">
              Dismiss
            </Button>
          </div>
        )}

        {/* Current Subscription */}
        <SubscriptionStatus
          subscription={subscription}
          onManage={handleManageBilling}
          onCancel={handleCancel}
          onResume={handleResume}
        />

        {/* Usage */}
        {usage && usage.metrics && Object.keys(usage.metrics).length > 0 && (
          <UsageCard
            usage={usage.metrics}
            periodStartsAt={usage.period_starts_at}
            periodEndsAt={usage.period_ends_at}
            onRefresh={handleRefreshUsage}
          />
        )}

        {/* Plan Selection */}
        <div>
          <h2 className="text-lg font-semibold text-foreground mb-4">Available Plans</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {plans.map((plan) => (
              <PlanCard
                key={plan.id}
                plan={plan}
                currentPlan={subscription?.plan}
                onSelect={handlePlanSelect}
                loading={actionLoading}
              />
            ))}
          </div>
        </div>

        <Separator />

        {/* Payment Methods */}
        <PaymentMethodList
          methods={paymentMethods}
          onRemove={async (id) => {
            try {
              await removePaymentMethod(id);
              setPaymentMethods((prev) => prev.filter((m) => m.id !== id));
            } catch (err) {
              setError("Failed to remove payment method");
            }
          }}
          onSetDefault={async (id) => {
            try {
              await setDefaultPaymentMethod(id);
              await fetchData();
            } catch (err) {
              setError("Failed to set default payment method");
            }
          }}
        />

        <Separator />

        {/* Invoices */}
        <InvoiceList invoices={invoices} loading={loading} />
      </div>
    </div>
  );
}

export default function BillingPage() {
  return (
    <ProtectedRoute>
      <BillingContent />
    </ProtectedRoute>
  );
}
