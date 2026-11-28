"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { useReplay } from "./ReplayProvider";
import { Plus, Minus, Pencil, ArrowRightLeft, Loader2 } from "lucide-react";
import { getReplayChanges } from "@/lib/api-replay";
import type { ReplayChangeItem } from "@/types/replay2";

function nearestScan(scans: { scan_id: string; timestamp: string }[], ts: string) {
  if (scans.length === 0) return null;
  const target = new Date(ts).getTime();
  let best = scans[0];
  let min = Math.abs(new Date(best.timestamp).getTime() - target);
  for (const s of scans) {
    const d = Math.abs(new Date(s.timestamp).getTime() - target);
    if (d < min) {
      min = d;
      best = s;
    }
  }
  return best;
}

type RowItem = Pick<ReplayChangeItem, "id" | "entity_key" | "entity_type">;

function ChangeRow({ item, icon: Icon, tone }: { item: RowItem; icon: any; tone: string }) {
  return (
    <div className={cn("flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs", tone)}>
      <Icon className="h-3 w-3 shrink-0" />
      <span className="font-mono truncate">{item.entity_key}</span>
      <span className="ml-auto text-[9px] uppercase text-muted-foreground">{item.entity_type}</span>
    </div>
  );
}

export function ChangeDetection() {
  const { state } = useReplay();
  const [changes, setChanges] =
    useState<Pick<ReplayChangeItem, "id" | "entity_key" | "entity_type">[] | null>(null);
  const [loading, setLoading] = useState(false);

  const fromScan = nearestScan(state.scans, state.fromTimestamp);
  const toScan = nearestScan(state.scans, state.toTimestamp);

  const computeDiff = async () => {
    if (!fromScan || !toScan) return;
    setLoading(true);
    try {
      const res = await getReplayChanges(fromScan.scan_id, toScan.scan_id);
      const all = [...res.added, ...res.removed, ...res.modified];
      setChanges(all.length > 0 ? all : []);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Changes Detected</h3>
        <button
          onClick={computeDiff}
          disabled={!fromScan || !toScan || loading}
          className="text-xs text-brand hover:text-brand/80 transition-colors disabled:opacity-40"
        >
          {loading ? <Loader2 className="h-3 w-3 inline animate-spin" /> : "Compute Diff"}
        </button>
      </div>

      {changes !== null ? (
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground">
            {changes.length} change(s) between selected scans.
          </p>
          {changes.length > 0 ? (
            <div className="grid grid-cols-3 gap-2">
              {changes.slice(0, 12).map((c) => (
                <ChangeRow
                  key={c.id}
                  item={c}
                  icon={c.entity_type === "removed" ? Minus : c.entity_type === "modified" ? Pencil : Plus}
                  tone={
                    c.entity_type === "removed"
                      ? "bg-destructive/5"
                      : c.entity_type === "modified"
                      ? "bg-warning/5"
                      : "bg-success/5"
                  }
                />
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">No recorded changes between these scans.</p>
          )}
        </div>
      ) : (
        <div className="flex flex-col items-center py-8 text-center">
          <ArrowRightLeft className="h-8 w-8 text-muted-foreground/30 mb-3" />
          <p className="text-xs text-muted-foreground">
            Select a date range and click Compute Diff to compare changes.
          </p>
        </div>
      )}
    </div>
  );
}
