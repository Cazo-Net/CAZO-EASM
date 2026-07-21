"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Shield,
  ShieldCheck,
  ShieldAlert,
  ShieldX,
} from "lucide-react";
import type { SecurityDashboard, SecurityFactor } from "@/types";

interface SecurityScoreProps {
  dashboard: SecurityDashboard;
  className?: string;
}

function getScoreColor(score: number) {
  if (score >= 80) return "text-success";
  if (score >= 60) return "text-warning";
  return "text-destructive";
}

function getScoreIcon(score: number) {
  if (score >= 80) return <ShieldCheck className="w-8 h-8" />;
  if (score >= 60) return <ShieldAlert className="w-8 h-8" />;
  return <ShieldX className="w-8 h-8" />;
}

function getFactorIcon(status: SecurityFactor["status"]) {
  switch (status) {
    case "good":
      return <ShieldCheck className="w-4 h-4 text-success" />;
    case "warning":
      return <ShieldAlert className="w-4 h-4 text-warning" />;
    case "critical":
      return <ShieldX className="w-4 h-4 text-destructive" />;
    default:
      return <Shield className="w-4 h-4 text-muted-foreground" />;
  }
}

export function SecurityScore({ dashboard, className }: SecurityScoreProps) {
  const { security_score } = dashboard;
  const score = security_score.score;

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-base font-semibold">Security Score</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-4">
          <div className={cn("p-3 rounded-full bg-muted", getScoreColor(score))}>
            {getScoreIcon(score)}
          </div>
          <div>
            <div className={cn("text-3xl font-bold", getScoreColor(score))}>
              {score}/100
            </div>
            <p className="text-sm text-muted-foreground">
              {score >= 80 ? "Excellent" : score >= 60 ? "Good" : "Needs improvement"}
            </p>
          </div>
        </div>

        <Progress
          value={score}
          className={cn(
            "h-3",
            score >= 80 && "[&>div]:bg-success",
            score >= 60 && score < 80 && "[&>div]:bg-warning",
            score < 60 && "[&>div]:bg-destructive"
          )}
        />

        <div className="space-y-3">
          {security_score.factors.map((factor) => (
            <div
              key={factor.name}
              className="flex items-start gap-3 p-3 rounded-lg border"
            >
              {getFactorIcon(factor.status)}
              <div className="flex-1">
                <p className="text-sm font-medium text-foreground">
                  {factor.name}
                  <span className="ml-2 text-xs text-muted-foreground">
                    +{factor.points} pts
                  </span>
                </p>
                {factor.detail && (
                  <p className="text-xs text-muted-foreground mt-1">{factor.detail}</p>
                )}
                {factor.recommendation && (
                  <p className="text-xs text-brand mt-1">
                    Recommendation: {factor.recommendation}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
