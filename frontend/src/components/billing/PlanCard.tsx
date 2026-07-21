"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Check, Zap, Star, Crown } from "lucide-react";
import type { Plan } from "@/types";

interface PlanCardProps {
  plan: Plan;
  currentPlan?: string;
  onSelect?: (planId: string) => void;
  loading?: boolean;
  className?: string;
}

const planIcons: Record<string, React.ReactNode> = {
  free_trial: <Zap className="w-5 h-5" />,
  free: <Star className="w-5 h-5" />,
  starter: <Zap className="w-5 h-5" />,
  professional: <Star className="w-5 h-5" />,
  enterprise: <Crown className="w-5 h-5" />,
};

const planAccents: Record<string, string> = {
  free_trial: "border-border bg-muted/30",
  free: "border-border bg-muted/30",
  starter: "border-brand/30 bg-brand/5",
  professional: "border-accent-2/30 bg-accent-2/5 ring-2 ring-accent-2/20",
  enterprise: "border-warning/30 bg-warning/5",
};

export function PlanCard({
  plan,
  currentPlan,
  onSelect,
  loading,
  className,
}: PlanCardProps) {
  const isCurrent = currentPlan === plan.id;
  const isUpgrade = !isCurrent;

  const handleSelect = () => {
    if (isUpgrade && onSelect) {
      onSelect(plan.id);
    }
  };

  return (
    <div
      className={cn(
        "relative rounded-xl border p-6 flex flex-col transition-all duration-200",
        planAccents[plan.id] || "border-border",
        isCurrent && "ring-2 ring-brand/40",
        isUpgrade && "hover:border-brand/50 hover:shadow-lg hover:shadow-brand/10 cursor-pointer",
        className
      )}
    >
      {isCurrent && (
        <Badge className="absolute -top-3 left-6 bg-brand text-white text-xs px-3 py-1">
          Current Plan
        </Badge>
      )}

      <div className="flex items-center gap-3 mb-4">
        <div className={cn("p-2 rounded-lg", planAccents[plan.id])}>
          {planIcons[plan.id] || <Zap className="w-5 h-5" />}
        </div>
        <div>
          <h3 className="text-lg font-semibold text-foreground">{plan.name}</h3>
          <p className="text-sm text-muted-foreground">{plan.description}</p>
        </div>
      </div>

      <div className="mb-6">
        {plan.price_monthly === 0 ? (
          <div className="text-3xl font-bold text-foreground">Free</div>
        ) : plan.price_monthly < 0 ? (
          <div className="text-3xl font-bold text-foreground">Custom</div>
        ) : (
          <div className="flex items-baseline gap-1">
            <span className="text-3xl font-bold text-foreground">
              ${plan.price_monthly}
            </span>
            <span className="text-muted-foreground">/mo</span>
          </div>
        )}
      </div>

      <div className="flex-1 space-y-2 mb-6">
        {plan.features.map((feature) => (
          <div key={feature} className="flex items-start gap-2 text-sm">
            <Check className="w-4 h-4 mt-0.5 text-brand shrink-0" />
            <span className="text-muted-foreground">{feature}</span>
          </div>
        ))}
      </div>

      {isUpgrade && (
        <Button
          onClick={handleSelect}
          disabled={loading}
          variant={plan.id === "enterprise" ? "outline" : "default"}
          className={cn(
            "w-full",
            plan.id === "professional" && "gradient-brand text-white hover:opacity-90"
          )}
        >
          {loading ? "Processing..." : plan.id === "enterprise" ? "Contact Sales" : plan.price_monthly === 0 ? "Downgrade" : "Upgrade"}
        </Button>
      )}

      {isCurrent && (
        <Button variant="outline" className="w-full" disabled>
          Your Current Plan
        </Button>
      )}
    </div>
  );
}
