"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  CreditCard,
  Trash2,
  CheckCircle,
  Plus,
} from "lucide-react";
import type { PaymentMethod } from "@/types";

interface PaymentMethodListProps {
  methods: PaymentMethod[];
  onRemove?: (id: string) => void;
  onSetDefault?: (id: string) => void;
  className?: string;
}

const brandIcons: Record<string, string> = {
  visa: "Visa",
  mastercard: "Mastercard",
  amex: "Amex",
  discover: "Discover",
  diners: "Diners Club",
  jcb: "JCB",
};

export function PaymentMethodList({
  methods,
  onRemove,
  onSetDefault,
  className,
}: PaymentMethodListProps) {
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-base font-semibold flex items-center gap-2">
          <CreditCard className="w-4 h-4" />
          Payment Methods
        </CardTitle>
      </CardHeader>
      <CardContent>
        {methods.length === 0 ? (
          <div className="text-center py-8 space-y-3">
            <CreditCard className="w-10 h-10 text-muted-foreground mx-auto" />
            <p className="text-sm text-muted-foreground">No payment methods added</p>
          </div>
        ) : (
          <div className="space-y-2">
            {methods.map((method) => (
              <div
                key={method.id}
                className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-7 rounded bg-muted flex items-center justify-center text-xs font-bold text-foreground">
                    {brandIcons[method.brand?.toLowerCase()] || method.brand?.slice(0, 4).toUpperCase()}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      {method.brand?.charAt(0).toUpperCase() + method.brand?.slice(1)} •••• {method.last4}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Expires {method.exp_month}/{method.exp_year}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {onSetDefault && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onSetDefault(method.id)}
                    >
                      <CheckCircle className="w-4 h-4" />
                    </Button>
                  )}
                  {onRemove && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onRemove(method.id)}
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
