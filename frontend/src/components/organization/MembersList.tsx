"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Users,
  UserPlus,
  Trash2,
  Mail,
  Clock,
  Shield,
} from "lucide-react";
import type { Invitation } from "@/types";

interface MembersListProps {
  members: Invitation[];
  onInvite?: () => void;
  onRevoke?: (id: string) => void;
  onResend?: (id: string) => void;
  className?: string;
}

const roleColors: Record<string, string> = {
  owner: "bg-warning/10 text-warning",
  admin: "bg-brand/10 text-brand",
  security_manager: "bg-success/10 text-success",
  analyst: "bg-info/10 text-info",
  viewer: "bg-muted text-muted-foreground",
};

export function MembersList({
  members,
  onInvite,
  onRevoke,
  onResend,
  className,
}: MembersListProps) {
  return (
    <Card className={className}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
        <CardTitle className="text-base font-semibold flex items-center gap-2">
          <Users className="w-4 h-4" />
          Team Members
        </CardTitle>
        {onInvite && (
          <Button size="sm" onClick={onInvite}>
            <UserPlus className="w-4 h-4 mr-2" />
            Invite
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {members.length === 0 ? (
          <div className="text-center py-8 space-y-3">
            <Users className="w-10 h-10 text-muted-foreground mx-auto" />
            <p className="text-sm text-muted-foreground">No team members yet</p>
          </div>
        ) : (
          <div className="space-y-2">
            {members.map((member) => (
              <div
                key={member.id}
                className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-xs font-semibold text-foreground">
                    {member.email?.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">{member.email}</p>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {new Date(member.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge className={cn("text-xs capitalize", roleColors[member.role])}>
                    {member.role?.replace("_", " ")}
                  </Badge>
                  {onResend && member.status === "pending" && (
                    <Button variant="ghost" size="sm" onClick={() => onResend(member.id)}>
                      <Mail className="w-4 h-4" />
                    </Button>
                  )}
                  {onRevoke && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onRevoke(member.id)}
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
