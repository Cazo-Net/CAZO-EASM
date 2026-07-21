"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  CheckCircle,
  XCircle,
  Globe,
  Clock,
} from "lucide-react";
import type { LoginHistoryEntry } from "@/types";

interface LoginHistoryProps {
  entries: LoginHistoryEntry[];
  className?: string;
}

export function LoginHistory({ entries, className }: LoginHistoryProps) {
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-base font-semibold">Login History</CardTitle>
      </CardHeader>
      <CardContent>
        {entries.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            No login history
          </p>
        ) : (
          <div className="space-y-2">
            {entries.map((entry) => (
              <div
                key={entry.id}
                className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  {entry.success ? (
                    <CheckCircle className="w-4 h-4 text-success" />
                  ) : (
                    <XCircle className="w-4 h-4 text-destructive" />
                  )}
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      {entry.event_type === "login" ? "Sign In" : entry.event_type}
                    </p>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      {entry.ip_address && (
                        <span className="flex items-center gap-1">
                          <Globe className="w-3 h-3" />
                          {entry.ip_address}
                        </span>
                      )}
                      {entry.created_at && (
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {new Date(entry.created_at).toLocaleString()}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <Badge
                  className={cn(
                    "text-xs",
                    entry.success
                      ? "bg-success/10 text-success"
                      : "bg-destructive/10 text-destructive"
                  )}
                >
                  {entry.success ? "Success" : "Failed"}
                </Badge>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
