"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Monitor,
  Smartphone,
  Globe,
  MapPin,
  Clock,
  Trash2,
  LogOut,
} from "lucide-react";
import type { SessionInfo } from "@/types";

interface SessionManagerProps {
  sessions: SessionInfo[];
  onRevoke?: (sessionId: string) => void;
  onRevokeAll?: () => void;
  className?: string;
}

export function SessionManager({
  sessions,
  onRevoke,
  onRevokeAll,
  className,
}: SessionManagerProps) {
  return (
    <Card className={className}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
        <CardTitle className="text-base font-semibold">Active Sessions</CardTitle>
        {onRevokeAll && sessions.length > 1 && (
          <Button variant="ghost" size="sm" onClick={onRevokeAll} className="text-destructive hover:text-destructive">
            <LogOut className="w-4 h-4 mr-2" />
            Revoke All
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {sessions.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            No active sessions
          </p>
        ) : (
          <div className="space-y-2">
            {sessions.map((session) => (
              <div
                key={session.id}
                className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-muted">
                    {session.os?.toLowerCase().includes("mobile") ||
                    session.os?.toLowerCase().includes("android") ||
                    session.os?.toLowerCase().includes("ios") ? (
                      <Smartphone className="w-4 h-4 text-foreground" />
                    ) : (
                      <Monitor className="w-4 h-4 text-foreground" />
                    )}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      {session.browser || "Unknown Browser"}
                      {session.os && ` on ${session.os}`}
                    </p>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      {session.ip_address && (
                        <span className="flex items-center gap-1">
                          <Globe className="w-3 h-3" />
                          {session.ip_address}
                        </span>
                      )}
                      {session.location_city && (
                        <span className="flex items-center gap-1">
                          <MapPin className="w-3 h-3" />
                          {session.location_city}
                          {session.location_country && `, ${session.location_country}`}
                        </span>
                      )}
                      {session.last_activity && (
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {new Date(session.last_activity).toLocaleString()}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {session.is_trusted && (
                    <Badge className="bg-success/10 text-success text-xs">Trusted</Badge>
                  )}
                  {onRevoke && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onRevoke(session.id)}
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
