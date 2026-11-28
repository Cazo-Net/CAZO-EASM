"use client";

import { cn } from "@/lib/utils";

/**
 * The hooded guard shown on 403 pages. Two copies of the artwork are
 * stacked: eyes open underneath, eyes closed on top, and the top one is
 * faded in for a moment every few seconds so the guard blinks.
 */
export function GhostGuard({ className }: { className?: string }) {
  return (
    <div
      className={cn("relative h-[281px] w-[200px] shrink-0", className)}
      role="img"
      aria-label="A hooded guard watching the door"
      data-testid="ghost-guard"
    >
      <div
        className="absolute left-1/2 top-[38%] h-[110%] w-[110%] -translate-x-1/2 -translate-y-1/2 rounded-full blur-3xl"
        style={{ background: "radial-gradient(circle, rgba(56,189,248,0.14) 0%, transparent 70%)" }}
        aria-hidden="true"
      />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/illustrations/ghost-403-open.png"
        alt=""
        draggable={false}
        className="absolute inset-0 h-full w-full select-none object-contain"
      />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/illustrations/ghost-403-closed.png"
        alt=""
        draggable={false}
        className="ghost-blink absolute inset-0 h-full w-full select-none object-contain"
      />
    </div>
  );
}
