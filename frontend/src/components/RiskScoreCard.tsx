"use client";

import { getRiskLabel, getRiskColor } from "@/types";
import { ShieldAlert, ShieldCheck } from "lucide-react";

interface RiskScoreCardProps {
  score: number;
  className?: string;
}

export function RiskScoreCard({ score, className }: RiskScoreCardProps) {
  const label = getRiskLabel(score);
  const colorClass = getRiskColor(score);

  const Icon = score <= 25 ? ShieldCheck : ShieldAlert;

  return (
    <div className={`rounded-xl border bg-card p-6 shadow-sm ${className}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground">
            Overall Risk Score
          </p>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-5xl font-bold tracking-tight">{score}</span>
            <span className="text-lg text-muted-foreground">/ 100</span>
          </div>
        </div>
        <div className={`rounded-2xl p-5 ${colorClass}`}>
          <Icon className="h-10 w-10" />
        </div>
      </div>
      <div className="mt-4">
        <span
          className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold ${colorClass}`}
        >
          {label} Risk
        </span>
      </div>
    </div>
  );
}
