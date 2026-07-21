"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectItem } from "@/components/ui/select";
import { UserPlus, X } from "lucide-react";

interface InviteFormProps {
  onInvite: (email: string, role: string) => void;
  onCancel?: () => void;
  loading?: boolean;
  className?: string;
}

const roles = [
  { value: "viewer", label: "Viewer" },
  { value: "analyst", label: "Analyst" },
  { value: "security_manager", label: "Security Manager" },
  { value: "billing_admin", label: "Billing Admin" },
  { value: "admin", label: "Admin" },
];

export function InviteForm({
  onInvite,
  onCancel,
  loading,
  className,
}: InviteFormProps) {
  const [email, setEmail] = React.useState("");
  const [role, setRole] = React.useState("viewer");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (email.trim()) {
      onInvite(email.trim(), role);
      setEmail("");
      setRole("viewer");
    }
  };

  return (
    <Card className={className}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
        <CardTitle className="text-base font-semibold flex items-center gap-2">
          <UserPlus className="w-4 h-4" />
          Invite Team Member
        </CardTitle>
        {onCancel && (
          <Button variant="ghost" size="sm" onClick={onCancel}>
            <X className="w-4 h-4" />
          </Button>
        )}
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Email Address</label>
            <Input
              type="email"
              placeholder="colleague@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Role</label>
            <Select value={role} onChange={(e) => setRole(e.target.value)}>
              {roles.map((r) => (
                <SelectItem key={r.value} value={r.value}>
                  {r.label}
                </SelectItem>
              ))}
            </Select>
          </div>
          <Button type="submit" disabled={loading || !email.trim()} className="w-full">
            {loading ? "Sending Invite..." : "Send Invitation"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
