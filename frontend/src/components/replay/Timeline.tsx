"use client";

import { useRef, useState, useCallback, useEffect } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { useReplay } from "./ReplayProvider";
import type { ReplayMode } from "@/types/replay";

const modeIntervals: Record<ReplayMode, number> = {
  hourly: 3600000,
  daily: 86400000,
  weekly: 604800000,
  monthly: 2592000000,
  quarterly: 7776000000,
  yearly: 31536000000,
};

function formatDate(ts: string, mode: ReplayMode): string {
  const d = new Date(ts);
  switch (mode) {
    case "hourly":
      return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
    case "daily":
      return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    case "weekly":
    case "monthly":
      return d.toLocaleDateString("en-US", { month: "short", year: "numeric" });
    case "quarterly":
      return `Q${Math.floor(d.getMonth() / 3) + 1} ${d.getFullYear()}`;
    case "yearly":
      return String(d.getFullYear());
  }
}

export function Timeline() {
  const { state, setTimestamp, jumpToScan } = useReplay();
  const trackRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState(false);
  const [hoverX, setHoverX] = useState<number | null>(null);

  const fromMs = new Date(state.fromTimestamp).getTime();
  const toMs = new Date(state.toTimestamp).getTime();
  const currentMs = new Date(state.currentTimestamp).getTime();
  const range = toMs - fromMs || 1;

  const getPositionFromTime = useCallback(
    (ts: string) => {
      const ms = new Date(ts).getTime();
      return ((ms - fromMs) / range) * 100;
    },
    [fromMs, range]
  );

  const getTimeFromPosition = useCallback(
    (pct: number) => {
      const ms = fromMs + (pct / 100) * range;
      return new Date(ms).toISOString();
    },
    [fromMs, range]
  );

  const handleTrackInteraction = useCallback(
    (clientX: number) => {
      if (!trackRef.current) return;
      const rect = trackRef.current.getBoundingClientRect();
      const pct = Math.max(0, Math.min(100, ((clientX - rect.left) / rect.width) * 100));
      setTimestamp(getTimeFromPosition(pct));
    },
    [setTimestamp, getTimeFromPosition]
  );

  const handleMouseDown = (e: React.MouseEvent) => {
    setDragging(true);
    handleTrackInteraction(e.clientX);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (dragging) handleTrackInteraction(e.clientX);
    if (trackRef.current) {
      const rect = trackRef.current.getBoundingClientRect();
      setHoverX(((e.clientX - rect.left) / rect.width) * 100);
    }
  };

  const handleMouseUp = () => setDragging(false);
  const handleMouseLeave = () => {
    setDragging(false);
    setHoverX(null);
  };

  useEffect(() => {
    const onUp = () => setDragging(false);
    const onMove = (e: MouseEvent) => {
      if (dragging) handleTrackInteraction(e.clientX);
    };
    window.addEventListener("mouseup", onUp);
    window.addEventListener("mousemove", onMove);
    return () => {
      window.removeEventListener("mouseup", onUp);
      window.removeEventListener("mousemove", onMove);
    };
  }, [dragging, handleTrackInteraction]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowRight") {
      e.preventDefault();
      const idx = state.scans.findIndex((s) => s.scan_id === state.selectedScan?.scan_id);
      if (idx < state.scans.length - 1) jumpToScan(state.scans[idx + 1].scan_id);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      const idx = state.scans.findIndex((s) => s.scan_id === state.selectedScan?.scan_id);
      if (idx > 0) jumpToScan(state.scans[idx - 1].scan_id);
    }
  };

  const scanPositions = state.scans.map((s) => ({
    ...s,
    pct: getPositionFromTime(s.timestamp),
  }));

  const bookMarkPositions = state.bookmarks.map((b) => ({
    ...b,
    pct: getPositionFromTime(b.timestamp),
  }));

  const eventPositions = state.events.map((ev) => ({
    ...ev,
    pct: getPositionFromTime(ev.timestamp),
  }));

  const currentPct = getPositionFromTime(state.currentTimestamp);

  return (
    <div className="w-full select-none" role="slider" aria-label="Replay timeline" tabIndex={0} onKeyDown={handleKeyDown}>
      {/* Date range labels */}
      <div className="mb-2 flex items-center justify-between text-[10px] text-muted-foreground">
        <span>{formatDate(state.fromTimestamp, state.mode)}</span>
        <span className="font-medium text-foreground">{formatDate(state.currentTimestamp, state.mode)}</span>
        <span>{formatDate(state.toTimestamp, state.mode)}</span>
      </div>

      {/* Timeline track */}
      <div
        ref={trackRef}
        className="relative h-12 cursor-pointer rounded-xl border border-border bg-card"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
      >
        {/* Scan tick marks */}
        {scanPositions.map((s) => (
          <button
            key={s.scan_id}
            className={cn(
              "absolute top-0 h-full w-px transition-colors",
              s.scan_id === state.selectedScan?.scan_id ? "bg-brand" : "bg-border/40 hover:bg-border"
            )}
            style={{ left: `${s.pct}%` }}
            onClick={(e) => {
              e.stopPropagation();
              jumpToScan(s.scan_id);
            }}
            title={s.scan_name || s.domain}
          />
        ))}

        {/* Event markers */}
        {eventPositions.map((ev) => (
          <div
            key={ev.id}
            className={cn(
              "absolute bottom-0 h-2 w-2 -translate-x-1/2 rounded-full",
              ev.severity === "critical" && "bg-destructive",
              ev.severity === "warning" && "bg-warning",
              ev.severity === "success" && "bg-success",
              ev.severity === "info" && "bg-info"
            )}
            style={{ left: `${ev.pct}%` }}
            title={ev.title}
          />
        ))}

        {/* Bookmark markers */}
        {bookMarkPositions.map((b) => (
          <div
            key={b.id}
            className="absolute top-0 h-full w-0.5 -translate-x-1/2 bg-accent-2"
            style={{ left: `${b.pct}%` }}
            title={b.name}
          />
        ))}

        {/* Progress fill */}
        <div
          className="absolute inset-y-0 left-0 rounded-l-xl bg-brand/10"
          style={{ width: `${currentPct}%` }}
        />

        {/* Hover indicator */}
        {hoverX !== null && (
          <div
            className="absolute inset-y-0 w-px bg-muted-foreground/30"
            style={{ left: `${hoverX}%` }}
          />
        )}

        {/* Playhead */}
        <motion.div
          className="absolute top-1/2 z-10 -translate-x-1/2 -translate-y-1/2"
          style={{ left: `${currentPct}%` }}
          animate={{ left: `${currentPct}%` }}
          transition={{ type: "spring", stiffness: 300, damping: 30 }}
        >
          <div className="h-5 w-5 rounded-full border-2 border-brand bg-background" />
        </motion.div>
      </div>

      {/* Scan labels below */}
      <div className="relative mt-1 h-4 overflow-hidden">
        {scanPositions
          .filter((_, i) => i % Math.max(1, Math.floor(scanPositions.length / 10)) === 0 || scanPositions[i]?.scan_id === state.selectedScan?.scan_id)
          .map((s) => (
            <span
              key={s.scan_id}
              className={cn(
                "absolute -translate-x-1/2 text-[9px]",
                s.scan_id === state.selectedScan?.scan_id ? "font-medium text-brand" : "text-muted-foreground"
              )}
              style={{ left: `${s.pct}%` }}
            >
              {new Date(s.timestamp).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
            </span>
          ))}
      </div>
    </div>
  );
}
