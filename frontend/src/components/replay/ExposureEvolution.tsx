"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { useReplay } from "./ReplayProvider";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

export function ExposureEvolution() {
  const { state } = useReplay();
  const history = state.exposureHistory;

  if (history.length === 0) {
    return (
      <div className="flex flex-col items-center py-8 text-center">
        <TrendingUp className="h-8 w-8 text-muted-foreground/30 mb-3" />
        <p className="text-xs text-muted-foreground">
          Exposure history will appear here as you navigate through scans.
        </p>
      </div>
    );
  }

  const maxScore = Math.max(...history.map((h) => h.score), 100);

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold">Exposure Evolution</h3>

      {/* Mini bar chart */}
      <div className="flex items-end gap-1 h-24">
        {history.map((h, i) => (
          <motion.div
            key={h.timestamp}
            initial={{ height: 0 }}
            animate={{ height: `${(h.score / maxScore) * 100}%` }}
            transition={{ delay: i * 0.05, duration: 0.3 }}
            className={cn(
              "flex-1 min-w-[4px] rounded-t-sm transition-colors",
              h.score > 60 ? "bg-destructive/60" : h.score > 30 ? "bg-warning/60" : "bg-success/60"
            )}
            title={`${new Date(h.timestamp).toLocaleDateString()} — Score: ${h.score}`}
          />
        ))}
      </div>

      {/* Recent entries */}
      <div className="space-y-2 max-h-60 overflow-y-auto">
        {history.slice(-10).reverse().map((h, i) => (
          <div key={h.timestamp} className="rounded-lg border border-border bg-card p-3">
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-muted-foreground">
                {new Date(h.timestamp).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
              </span>
              <div className="flex items-center gap-1.5">
                {h.delta > 0 ? (
                  <TrendingUp className="h-3 w-3 text-destructive" />
                ) : h.delta < 0 ? (
                  <TrendingDown className="h-3 w-3 text-success" />
                ) : (
                  <Minus className="h-3 w-3 text-muted-foreground" />
                )}
                <span className={cn(
                  "text-xs font-semibold",
                  h.delta > 0 ? "text-destructive" : h.delta < 0 ? "text-success" : "text-muted-foreground"
                )}>
                  {h.score}
                </span>
              </div>
            </div>
            {h.reasons.length > 0 && (
              <div className="mt-2 space-y-0.5">
                {h.reasons.slice(0, 2).map((r) => (
                  <p key={r} className="text-[10px] text-muted-foreground leading-relaxed">• {r}</p>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
