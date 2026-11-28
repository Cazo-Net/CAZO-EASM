"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, Clock, Loader2, XCircle } from "lucide-react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { Button } from "@/components/ui/button";
import { billingErrorMessage, formatMoney, getCheckoutStatus } from "@/lib/api-billing";

type Status = Awaited<ReturnType<typeof getCheckoutStatus>>;

function SuccessInner() {
  const params = useSearchParams();
  const sessionId = params.get("session_id");
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!sessionId) {
      setError("Missing checkout reference.");
      return;
    }
    let tries = 0;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const s = await getCheckoutStatus(sessionId);
        setStatus(s);
        // Some bank payments confirm a few seconds after the redirect.
        if (s.payment_status === "unpaid" && s.status === "complete" && tries++ < 10) {
          timer = setTimeout(poll, 3000);
        }
      } catch (e) {
        setError(billingErrorMessage(e, "We could not confirm this payment."));
      }
    };
    poll();
    return () => clearTimeout(timer);
  }, [sessionId]);

  const paid = status && (status.payment_status === "paid" || status.payment_status === "no_payment_required");
  const pending = status && !paid && status.status === "complete";

  return (
    <div className="mx-auto flex max-w-lg flex-col items-center p-10 text-center">
      {!status && !error && <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />}
      {error && (
        <>
          <XCircle className="h-10 w-10 text-red-400" />
          <h1 className="mt-4 text-2xl font-semibold">Payment not confirmed</h1>
          <p className="mt-2 text-sm text-muted-foreground">{error}</p>
        </>
      )}
      {paid && (
        <>
          <CheckCircle2 className="h-10 w-10 text-phosphor" />
          <h1 className="mt-4 text-2xl font-semibold">You&apos;re all set</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {status?.amount_total != null && status.currency
              ? `${formatMoney(status.amount_total, status.currency)} paid. `
              : ""}
            Your plan is active and the new limits apply now. A receipt is on its way by email.
          </p>
        </>
      )}
      {pending && (
        <>
          <Clock className="h-10 w-10 text-amber-400" />
          <h1 className="mt-4 text-2xl font-semibold">Payment processing</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Your bank is still confirming the payment. Your plan switches on as soon as it clears.
          </p>
        </>
      )}
      {status && !paid && !pending && (
        <>
          <XCircle className="h-10 w-10 text-red-400" />
          <h1 className="mt-4 text-2xl font-semibold">Checkout not finished</h1>
          <p className="mt-2 text-sm text-muted-foreground">Nothing was charged. You can try again.</p>
        </>
      )}
      <div className="mt-8 flex gap-2">
        <Button asChild>
          <Link href="/billing">Go to billing</Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="/dashboard">Dashboard</Link>
        </Button>
      </div>
    </div>
  );
}

export default function CheckoutSuccessPage() {
  return (
    <ProtectedRoute>
      <Suspense fallback={null}>
        <SuccessInner />
      </Suspense>
    </ProtectedRoute>
  );
}
