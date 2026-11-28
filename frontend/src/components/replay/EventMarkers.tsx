"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { useReplay } from "./ReplayProvider";
import {
  AlertTriangle,
  CheckCircle2,
  Info,
  AlertOctagon,
  Plus,
  Minus,
  RefreshCw,
  Wifi,
  WifiOff,
} from "lucide-react";

const severityIcons: Record<string, any> = {
  critical: AlertOctagon,
  warning: AlertTriangle,
  success: CheckCircle2,
  info: Info,
};

const severityColors: Record<string, string> = {
  critical: "text-destructive bg-destructive/10 border-destructive/20",
  warning: "text-warning bg-warning/10 border-warning/20",
  success: "text-success bg-success/10 border-success/20",
  info: "text-info bg-info/10 border-info/20",
};

export function EventMarkers() {
  const { state, setTimestamp } = useReplay();

  if (state.events.length === 0) {
    return (
      <div className="flex flex-col items-center py-8 text-center">
        <Info className="h-8 w-8 text-muted-foreground/30 mb-3" />
        <p className="text-xs text-muted-foreground">
          Events will appear as you navigate through scan history.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold">Timeline Events</h3>
      <div className="space-y-2 max-h-80 overflow-y-auto">
        {state.events.map((ev, i) => {
          const Icon = severityIcons[ev.severity] || Info;
          return (
            <motion.button
              key={ev.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.03 }}
              onClick={() => setTimestamp(ev.timestamp)}
              className={cn(
                "w-full flex items-start gap-2.5 rounded-lg border p-2.5 text-left transition-colors hover:bg-card",
                severityColors[ev.severity]
              )}
            >
              <Icon className="h-3.5 w-3.5 mt-0.5 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium">{ev.title}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5 line-clamp-2">{ev.description}</p>
                <p className="text-[9px] text-muted-foreground mt-1">
                  {new Date(ev.timestamp).toLocaleString("en-US", {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </p>
              </div>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}
