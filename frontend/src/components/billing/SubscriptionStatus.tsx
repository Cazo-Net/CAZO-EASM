"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Calendar,
  Clock,
  AlertTriangle,
  ExternalLink,
  CreditCard,
} from "lucide-react";
import type { Subscription } from "@/types";

interface SubscriptionStatusProps {
  subscription: Subscription | null;
  onManage?: () => void;
  onCancel?: () => void;
  onResume?: () => void;
  className?: string;
}

const statusConfig: Record<string, { label: string; color: string }> = {
  active: { label: "Active", color: "bg-success/10 text-success" },
  trial: { label: "Trial", color: "bg-brand/10 text-brand" },
  past_due: { label: "Past Due", color: "bg-warning/10 text-warning" },
  canceled: { label: "Canceled", color: "bg-destructive/10 text-destructive" },
  unpaid: { label: "Unpaid", color: "bg-destructive/10 text-destructive" },
};

export function SubscriptionStatus({
  subscription,
  onManage,
  onCancel,
  onResume,
  className,
}: SubscriptionStatusProps) {
  if (!subscription) {
    return (
      <Card className={className}>
        <CardContent className="flex items-center justify-center py-8">
          <p className="text-sm text-muted-foreground">No active subscription</p>
        </CardContent>
      </Card>
    );
  }

  const status = statusConfig[subscription.status] || statusConfig.active;
  const trialEnds = subscription.trial_ends_at
    ? new Date(subscription.trial_ends_at)
    : null;
  const isTrial = subscription.status === "trial";
  const isCanceled = subscription.status === "canceled";
  const isPastDue = subscription.status === "past_due";

  return (
    <Card className={className}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
        <CardTitle className="text-base font-semibold">Subscription</CardTitle>
        <Badge className={status.color}>{status.label}</Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        {isTrial && trialEnds && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-brand/5 border border-brand/20">
            <Clock className="w-4 h-4 text-brand" />
            <span className="text-sm text-foreground">
              Trial ends on {trialEnds.toLocaleDateString()}
            </span>
          </div>
        )}

        {isPastDue && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-warning/5 border border-warning/20">
            <AlertTriangle className="w-4 h-4 text-warning" />
            <span className="text-sm text-foreground">
              Payment is past due. Please update your payment method.
            </span>
          </div>
        )}

        {subscription.current_period_starts_at && subscription.current_period_ends_at && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Calendar className="w-4 h-4" />
            <span>
              Current period: {new Date(subscription.current_period_starts_at).toLocaleDateString()} -{" "}
              {new Date(subscription.current_period_ends_at).toLocaleDateString()}
            </span>
          </div>
        )}

        {subscription.canceled_at && (
          <p className="text-sm text-destructive">
            Canceled on {new Date(subscription.canceled_at).toLocaleDateString()}
            {subscription.cancel_at_period_end && " (ends at period end)"}
          </p>
        )}

        <div className="flex gap-2 pt-2">
          {onManage && (
            <Button variant="outline" size="sm" onClick={onManage}>
              <CreditCard className="w-4 h-4 mr-2" />
              Manage Billing
            </Button>
          )}
          {isCanceled && onResume && (
            <Button size="sm" onClick={onResume}>
              Resume Subscription
            </Button>
          )}
          {!isCanceled && onCancel && !isTrial && (
            <Button variant="ghost" size="sm" onClick={onCancel} className="text-destructive hover:text-destructive">
              Cancel Subscription
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
