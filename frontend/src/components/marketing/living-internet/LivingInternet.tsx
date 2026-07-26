"use client";

/**
 * LivingInternet — premium interactive "Internet is being mapped" background
 * for the CAZO landing hero. Custom PixiJS (WebGL) engine; not a particle
 * library. See engine.ts for the simulation.
 *
 * Integration: mounted behind the first hero viewport (fixed to its own box).
 * Fades out as the visitor scrolls into the product sequence, pauses when the
 * tab is hidden, and collapses to a single static glow frame under
 * prefers-reduced-motion.
 */

import { useEffect, useRef, useState, type RefObject } from "react";
import type { EngineHandle } from "./engine";

interface Props {
  /** Scroll container to derive the fade-out (the landing scroll box). */
  scrollContainerRef?: RefObject<HTMLElement>;
  /** Selector for the hero headline to avoid overlapping. */
  exclusionSelector?: string;
  className?: string;
}

export function LivingInternet({
  scrollContainerRef,
  exclusionSelector = "[data-hero-headline]",
  className = "",
}: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const engineRef = useRef<EngineHandle | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let disposed = false;

    (async () => {
      try {
        const { createEngine } = await import("./engine");
        if (disposed) return;
        const exclusionEl = document.querySelector<HTMLElement>(exclusionSelector);
        const engine = await createEngine({
          container: host,
          reducedMotion: reduced,
          exclusion: exclusionEl?.getBoundingClientRect() ?? null,
        });
        if (disposed) {
          engine.destroy();
          return;
        }
        engineRef.current = engine;
      } catch {
        setFailed(true);
      }
    })();

    return () => {
      disposed = true;
      engineRef.current?.destroy();
      engineRef.current = null;
    };
  }, [exclusionSelector]);

  // visibility pause
  useEffect(() => {
    const onVis = () => engineRef.current?.setPaused(document.hidden);
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  // keep exclusion rect fresh on resize
  useEffect(() => {
    const update = () => {
      const el = document.querySelector<HTMLElement>(exclusionSelector);
      engineRef.current?.setExclusion(el?.getBoundingClientRect() ?? null);
    };
    window.addEventListener("resize", update);
    const t = window.setInterval(update, 1500);
    return () => {
      window.removeEventListener("resize", update);
      window.clearInterval(t);
    };
  }, [exclusionSelector]);

  // scroll-driven fade-out (background belongs to the first viewport)
  useEffect(() => {
    const scroller = scrollContainerRef?.current ?? window;
    const getScroll = () =>
      scroller === window
        ? window.scrollY
        : (scroller as HTMLElement).scrollTop;
    const getVH = () =>
      scroller === window ? window.innerHeight : (scroller as HTMLElement).clientHeight;

    let raf = 0;
    const onScroll = () => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        const y = getScroll();
        const vh = getVH();
        // full opacity across the first viewport, fade to 0 by 1.4vh
        const a = Math.max(0, Math.min(1, 1 - y / (vh * 1.4)));
        engineRef.current?.setGlobalAlpha(a);
      });
    };
    scroller.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => {
      scroller.removeEventListener("scroll", onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [scrollContainerRef]);

  if (failed) {
    return (
      <div
        className={`pointer-events-none absolute inset-0 ${className}`}
        aria-hidden="true"
        style={{
          background:
            "radial-gradient(60% 50% at 50% 42%, rgba(24,242,178,0.08), transparent 70%), #050608",
        }}
      />
    );
  }

  return (
    <div
      ref={hostRef}
      aria-hidden="true"
      className={`absolute inset-0 overflow-hidden ${className}`}
      style={{ background: "#050608" }}
    />
  );
}
