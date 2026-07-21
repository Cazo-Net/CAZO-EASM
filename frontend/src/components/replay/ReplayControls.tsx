"use client";

import { motion } from "framer-motion";
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  ChevronsLeft,
  ChevronsRight,
  Clock,
  Calendar,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useReplay } from "./ReplayProvider";
import type { ReplayMode, ReplaySpeed } from "@/types/replay";

const speeds: ReplaySpeed[] = [0.25, 0.5, 1, 2, 4, 8];
const modes: { value: ReplayMode; label: string }[] = [
  { value: "hourly", label: "Hourly" },
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "quarterly", label: "Quarterly" },
  { value: "yearly", label: "Yearly" },
];

export function ReplayControls() {
  const { state, play, pause, stepForward, stepBackward, setSpeed, setMode } = useReplay();

  const currentIdx = state.scans.findIndex((s) => s.scan_id === state.selectedScan?.scan_id);

  return (
    <div className="flex flex-wrap items-center gap-3">
      {/* Playback controls */}
      <div className="flex items-center gap-1 rounded-xl border border-border/30 bg-card/20 p-1 backdrop-blur-sm">
        <button
          onClick={() => {
            if (state.scans.length > 0) {
              const first = state.scans[0];
              const { useReplay: _ } = require("./ReplayProvider");
            }
          }}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted/30 hover:text-foreground transition-colors"
          title="Go to start"
        >
          <ChevronsLeft className="h-4 w-4" />
        </button>

        <button
          onClick={stepBackward}
          disabled={currentIdx <= 0}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted/30 hover:text-foreground transition-colors disabled:opacity-30"
          title="Previous scan"
        >
          <SkipBack className="h-4 w-4" />
        </button>

        <motion.button
          whileTap={{ scale: 0.95 }}
          onClick={state.isPlaying ? pause : play}
          className={cn(
            "flex h-9 w-9 items-center justify-center rounded-xl transition-all",
            state.isPlaying
              ? "bg-brand text-white shadow-lg shadow-brand/20"
              : "bg-brand/10 text-brand hover:bg-brand/20"
          )}
          title={state.isPlaying ? "Pause" : "Play"}
        >
          {state.isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 ml-0.5" />}
        </motion.button>

        <button
          onClick={stepForward}
          disabled={currentIdx >= state.scans.length - 1}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted/30 hover:text-foreground transition-colors disabled:opacity-30"
          title="Next scan"
        >
          <SkipForward className="h-4 w-4" />
        </button>

        <button
          onClick={() => {
            if (state.scans.length > 0) {
              const last = state.scans[state.scans.length - 1];
            }
          }}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted/30 hover:text-foreground transition-colors"
          title="Go to end"
        >
          <ChevronsRight className="h-4 w-4" />
        </button>
      </div>

      {/* Speed selector */}
      <div className="flex items-center gap-1 rounded-xl border border-border/30 bg-card/20 p-1 backdrop-blur-sm">
        {speeds.map((s) => (
          <button
            key={s}
            onClick={() => setSpeed(s)}
            className={cn(
              "rounded-lg px-2 py-1 text-xs font-medium transition-colors",
              state.speed === s
                ? "bg-brand/10 text-brand"
                : "text-muted-foreground hover:bg-muted/30 hover:text-foreground"
            )}
          >
            {s}×
          </button>
        ))}
      </div>

      {/* Mode selector */}
      <div className="flex items-center gap-1 rounded-xl border border-border/30 bg-card/20 p-1 backdrop-blur-sm">
        {modes.map((m) => (
          <button
            key={m.value}
            onClick={() => setMode(m.value)}
            className={cn(
              "rounded-lg px-2.5 py-1 text-xs font-medium transition-colors",
              state.mode === m.value
                ? "bg-brand/10 text-brand"
                : "text-muted-foreground hover:bg-muted/30 hover:text-foreground"
            )}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* Scan counter */}
      <div className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
        <Clock className="h-3.5 w-3.5" />
        <span>
          {currentIdx >= 0 ? currentIdx + 1 : "—"} / {state.scans.length} scans
        </span>
      </div>
    </div>
  );
}
