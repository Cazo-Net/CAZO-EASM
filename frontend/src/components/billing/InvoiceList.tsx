"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Download, ExternalLink, Receipt, AlertCircle } from "lucide-react";
import type { Invoice } from "@/types";

interface InvoiceListProps {
  invoices: Invoice[];
  loading?: boolean;
  className?: string;
}

const statusColors: Record<string, string> = {
  paid: "bg-success/10 text-success",
  open: "bg-brand/10 text-brand",
  void: "bg-muted text-muted-foreground",
 uncollectible: "bg-destructive/10 text-destructive",
};

export function InvoiceList({ invoices, loading, className }: InvoiceListProps) {
  if (loading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="text-base font-semibold">Invoices</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-12 bg-muted animate-pulse rounded-lg" />
          ))}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-base font-semibold flex items-center gap-2">
          <Receipt className="w-4 h-4" />
          Invoices
        </CardTitle>
      </CardHeader>
      <CardContent>
        {invoices.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            No invoices yet
          </p>
        ) : (
          <div className="space-y-2">
            {invoices.map((inv) => (
              <div
                key={inv.id}
                className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-4">
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      ${(inv.amount_cents / 100).toFixed(2)} {inv.currency.toUpperCase()}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {inv.period_starts_at && inv.period_ends_at
                        ? `${new Date(inv.period_starts_at).toLocaleDateString()} - ${new Date(inv.period_ends_at).toLocaleDateString()}`
                        : new Date(inv.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <Badge
                    className={cn(
                      "text-xs capitalize",
                      statusColors[inv.status] || "bg-muted text-muted-foreground"
                    )}
                  >
                    {inv.status}
                  </Badge>
                  {inv.invoice_url && (
                    <a
                      href={inv.invoice_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <Button variant="ghost" size="sm">
                        <ExternalLink className="w-4 h-4" />
                      </Button>
                    </a>
                  )}
                  {inv.invoice_pdf_url && (
                    <a
                      href={inv.invoice_pdf_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <Button variant="ghost" size="sm">
                        <Download className="w-4 h-4" />
                      </Button>
                    </a>
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
