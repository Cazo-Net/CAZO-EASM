"use client";

/**
 * LandingIntro — a cinematic "boot / scan" sequence shown before the CAZO
 * landing hero is revealed.
 *
 * Composition (layered, ~3.2s):
 *   perspective grid → rotating radar sweep → CazoMark ring draws on →
 *   scan node ignites with expanding rings → discovery blips light up around
 *   the perimeter → wordmark + boot log + progress bar resolve → "scan
 *   complete" flash → the whole scene wipes/dissolves to reveal the hero.
 *
 * Behaviour: plays once per browser session (sessionStorage), skippable via
 * click / scroll / key, reduced-motion → instant reveal. Append ?intro=1 to
 * force-replay.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

const SESSION_KEY = "cazo_intro_seen";
const DURATION = 5200;
const EASE = [0.22, 1, 0.36, 1] as const;

const BOOT_LINES = [
  "initializing surface engine",
  "resolving perimeter",
  "correlating shared infrastructure",
  "mapping the internet",
];

const C = {
  bg: "#050608",
  primary: "#18F2B2",
  secondary: "#00D9FF",
  highlight: "#7A5CFF",
  soft: "#E8EDF5",
};

export function LandingIntro() {
  const [show, setShow] = useState(false);
  const [exiting, setExiting] = useState(false);
  const timers = useRef<number[]>([]);

  const dismiss = useCallback(() => {
    setExiting(true);
    try {
      sessionStorage.setItem(SESSION_KEY, "1");
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    const force =
      new URLSearchParams(window.location.search).get("intro") === "1";
    if (force) {
      try {
        sessionStorage.removeItem(SESSION_KEY);
      } catch {
        /* ignore */
      }
    }

    let seen = false;
    try {
      seen = sessionStorage.getItem(SESSION_KEY) === "1";
    } catch {
      /* ignore */
    }
    const reduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    if ((seen || reduced) && !force) {
      try {
        sessionStorage.setItem(SESSION_KEY, "1");
      } catch {
        /* ignore */
      }
      return;
    }

    setShow(true);
    const prevOverflow = document.documentElement.style.overflow;
    document.documentElement.style.overflow = "hidden";
    timers.current.push(window.setTimeout(dismiss, DURATION));

    return () => {
      document.documentElement.style.overflow = prevOverflow;
      timers.current.forEach((t) => window.clearTimeout(t));
      timers.current = [];
    };
  }, [dismiss]);

  useEffect(() => {
    if (!show) return;
    const skip = () => dismiss();
    window.addEventListener("keydown", skip);
    window.addEventListener("wheel", skip, { passive: true });
    window.addEventListener("touchmove", skip, { passive: true });
    return () => {
      window.removeEventListener("keydown", skip);
      window.removeEventListener("wheel", skip);
      window.removeEventListener("touchmove", skip);
    };
  }, [show, dismiss]);

  const handleExited = () => {
    setShow(false);
    document.documentElement.style.overflow = "";
  };

  return (
    <AnimatePresence onExitComplete={handleExited}>
      {show && !exiting && (
        <motion.div
          key="cazo-intro"
          className="fixed inset-0 z-[200] flex flex-col items-center justify-center overflow-hidden"
          style={{ background: C.bg }}
          initial={{ opacity: 1 }}
          exit={{ opacity: 0, filter: "blur(6px)" }}
          transition={{ duration: 0.85, ease: EASE }}
          onClick={dismiss}
          role="presentation"
        >
          {/* exit wipe — a phosphor line sweeps up as the scene leaves */}
          <ScenePlate />

          <Backdrop />
          <RadarSweep />
          <ScanRings />

          {/* centerpiece */}
          <div className="relative flex flex-col items-center">
            <div className="relative">
              <DiscoveryBlips />
              <IntroMark />
            </div>

            <motion.div
              className="mt-8 flex items-baseline gap-3"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1.7, duration: 0.9, ease: EASE }}
            >
              <span
                className="font-display text-4xl font-semibold tracking-tight md:text-5xl"
                style={{ color: C.soft }}
              >
                CAZO
              </span>
              <span
                className="font-mono text-[10px] uppercase tracking-[0.4em]"
                style={{ color: `${C.primary}b0` }}
              >
                EASM
              </span>
            </motion.div>

            <div className="mt-7 h-5">
              <BootLog />
            </div>

            <ProgressBar />
          </div>

          <motion.button
            type="button"
            onClick={dismiss}
            className="absolute bottom-8 left-1/2 -translate-x-1/2 font-mono text-[10px] uppercase tracking-[0.3em] transition-colors"
            style={{ color: `${C.soft}55` }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 2.4, duration: 0.6 }}
            whileHover={{ color: `${C.soft}aa` }}
          >
            skip intro
          </motion.button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/* ── exit plate: a bright line that sweeps to reveal the page ───────── */

function ScenePlate() {
  return (
    <motion.div
      aria-hidden
      className="pointer-events-none absolute inset-x-0 z-10 h-px"
      style={{
        background: `linear-gradient(90deg, transparent, ${C.primary}, transparent)`,
        boxShadow: `0 0 24px 2px ${C.primary}`,
      }}
      initial={{ top: "50%", opacity: 0 }}
      animate={{ opacity: [0, 0, 1], top: ["50%", "50%", "-4%"] }}
      transition={{ duration: DURATION / 1000, times: [0, 0.88, 1], ease: EASE }}
    />
  );
}

/* ── backdrop: perspective grid + vignette + grain ─────────────────── */

function Backdrop() {
  return (
    <>
      {/* radial ambient */}
      <motion.div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-1/2 h-[46rem] w-[46rem] -translate-x-1/2 -translate-y-1/2 rounded-full"
        style={{
          background: `radial-gradient(circle, ${C.primary}1a, ${C.secondary}0a 42%, transparent 70%)`,
        }}
        initial={{ opacity: 0, scale: 0.7 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 2.2, ease: EASE }}
      />
      {/* faint grid */}
      <motion.div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage: `linear-gradient(${C.secondary}14 1px, transparent 1px), linear-gradient(90deg, ${C.secondary}14 1px, transparent 1px)`,
          backgroundSize: "44px 44px",
          maskImage:
            "radial-gradient(ellipse 60% 55% at 50% 50%, #000 30%, transparent 75%)",
          WebkitMaskImage:
            "radial-gradient(ellipse 60% 55% at 50% 50%, #000 30%, transparent 75%)",
        }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 0.6 }}
        transition={{ duration: 1.8, ease: EASE }}
      />
      {/* vignette */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.55) 100%)",
        }}
      />
    </>
  );
}

/* ── rotating radar sweep behind the mark ──────────────────────────── */

function RadarSweep() {
  return (
    <motion.div
      aria-hidden
      className="pointer-events-none absolute left-1/2 top-1/2 h-[26rem] w-[26rem] -translate-x-1/2 -translate-y-1/2 rounded-full"
      style={{
        background: `conic-gradient(from 0deg, transparent 0deg, ${C.primary}00 300deg, ${C.primary}33 350deg, ${C.primary}66 360deg)`,
        maskImage: "radial-gradient(circle, #000 68%, transparent 70%)",
        WebkitMaskImage: "radial-gradient(circle, #000 68%, transparent 70%)",
      }}
      initial={{ opacity: 0, rotate: 0 }}
      animate={{ opacity: [0, 0.9, 0.9, 0], rotate: 1080 }}
      transition={{ duration: 4.4, times: [0, 0.12, 0.85, 1], ease: "linear" }}
    />
  );
}

/* ── concentric scan rings emitted from the node ───────────────────── */

function ScanRings() {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
    >
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="absolute left-1/2 top-1/2 block -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{ border: `1px solid ${C.primary}` }}
          initial={{ width: 40, height: 40, opacity: 0 }}
          animate={{ width: 520, height: 520, opacity: [0, 0.35, 0] }}
          transition={{
            delay: 1.4 + i * 0.7,
            duration: 3,
            ease: "easeOut",
            repeat: Infinity,
            repeatDelay: 0.5,
          }}
        />
      ))}
    </div>
  );
}

/* ── discovery blips lighting up around the ring ───────────────────── */

function DiscoveryBlips() {
  const blips = useMemo(
    () =>
      Array.from({ length: 7 }).map((_, i) => {
        const a = (i / 7) * Math.PI * 2 + 0.4;
        const R = 74;
        return {
          x: Math.cos(a) * R,
          y: Math.sin(a) * R,
          delay: 1.5 + i * 0.18,
          color: i % 3 === 0 ? C.secondary : i % 3 === 1 ? C.primary : C.highlight,
        };
      }),
    [],
  );
  return (
    <div className="pointer-events-none absolute left-1/2 top-1/2 z-10 h-0 w-0">
      {blips.map((b, i) => (
        <motion.span
          key={i}
          className="absolute block h-1.5 w-1.5 rounded-full"
          style={{
            background: b.color,
            boxShadow: `0 0 8px 1px ${b.color}`,
            left: b.x,
            top: b.y,
          }}
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: [0, 1.6, 1], opacity: [0, 1, 0.85] }}
          transition={{ delay: b.delay, duration: 0.7, ease: EASE }}
        />
      ))}
    </div>
  );
}

/* ── the CazoMark, drawn on ────────────────────────────────────────── */

function IntroMark() {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
      className="relative z-10 h-28 w-28 md:h-32 md:w-32"
      style={{ filter: `drop-shadow(0 0 18px ${C.primary}55)` }}
    >
      <defs>
        <linearGradient
          id="intro-ring"
          x1="4"
          y1="4"
          x2="28"
          y2="28"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor={C.primary} />
          <stop offset="1" stopColor={C.secondary} />
        </linearGradient>
        <radialGradient id="intro-sweep" cx="0.5" cy="0.5" r="0.5">
          <stop stopColor={C.primary} stopOpacity="0.45" />
          <stop offset="1" stopColor={C.primary} stopOpacity="0" />
        </radialGradient>
      </defs>

      <motion.circle
        cx="16"
        cy="16"
        r="13"
        fill="url(#intro-sweep)"
        initial={{ opacity: 0, scale: 0.6 }}
        animate={{ opacity: [0, 0.9, 0.5], scale: [0.6, 1.05, 1] }}
        transition={{ delay: 0.7, duration: 1.6, ease: EASE }}
        style={{ transformOrigin: "16px 16px" }}
      />

      <motion.path
        d="M23.5 7.6A11 11 0 1 0 27 16"
        stroke="url(#intro-ring)"
        strokeWidth="2.2"
        strokeLinecap="round"
        initial={{ pathLength: 0, opacity: 0.25 }}
        animate={{ pathLength: 1, opacity: 1 }}
        transition={{ delay: 0.3, duration: 1.8, ease: [0.65, 0, 0.35, 1] }}
      />

      <motion.path
        d="M16 4.5v2.2"
        stroke={C.primary}
        strokeWidth="1.4"
        strokeLinecap="round"
        initial={{ opacity: 0 }}
        animate={{ opacity: 0.6 }}
        transition={{ delay: 1.5, duration: 0.6 }}
      />
      <motion.path
        d="M27.5 16h-2.2"
        stroke={C.secondary}
        strokeWidth="1.4"
        strokeLinecap="round"
        initial={{ opacity: 0 }}
        animate={{ opacity: 0.6 }}
        transition={{ delay: 1.65, duration: 0.6 }}
      />

      <motion.circle
        cx="27"
        cy="16"
        r="2.6"
        fill={C.primary}
        initial={{ scale: 0, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{
          delay: 1.7,
          type: "spring",
          stiffness: 260,
          damping: 15,
        }}
        style={{ transformOrigin: "27px 16px" }}
      />
      <motion.circle
        cx="27"
        cy="16"
        r="4.4"
        stroke={C.primary}
        strokeWidth="1"
        initial={{ scale: 0.4, opacity: 0.9 }}
        animate={{ scale: 2.4, opacity: 0 }}
        transition={{ delay: 1.75, duration: 1.4, ease: "easeOut", repeat: 1, repeatDelay: 0.3 }}
        style={{ transformOrigin: "27px 16px" }}
      />
    </svg>
  );
}

/* ── boot log: char-by-char lines with a cursor ────────────────────── */

function BootLog() {
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    const t: number[] = [];
    BOOT_LINES.forEach((_, i) => {
      t.push(window.setTimeout(() => setIdx(i), 1600 + i * 800));
    });
    return () => t.forEach((x) => window.clearTimeout(x));
  }, []);

  return (
    <div className="relative h-5 w-[19rem] text-center">
      <AnimatePresence mode="wait">
        <motion.p
          key={idx}
          className="absolute inset-0 font-mono text-[11px] tracking-wide"
          style={{ color: `${C.soft}80` }}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.28 }}
        >
          <span style={{ color: C.primary }}>›</span>{" "}
          <Typewriter text={BOOT_LINES[idx]} />
          <motion.span
            aria-hidden
            style={{ color: C.primary }}
            animate={{ opacity: [1, 0.15, 1] }}
            transition={{ duration: 0.9, repeat: Infinity }}
          >
            _
          </motion.span>
        </motion.p>
      </AnimatePresence>
    </div>
  );
}

function Typewriter({ text }: { text: string }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    setN(0);
    const id = window.setInterval(() => {
      setN((p) => {
        if (p >= text.length) {
          window.clearInterval(id);
          return p;
        }
        return p + 1;
      });
    }, 34);
    return () => window.clearInterval(id);
  }, [text]);
  return <span>{text.slice(0, n)}</span>;
}

/* ── progress bar tied to the overall timeline ─────────────────────── */

function ProgressBar() {
  return (
    <motion.div
      className="mt-7 h-[3px] w-56 overflow-hidden rounded-full"
      style={{ background: `${C.soft}12` }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.9, duration: 0.4 }}
    >
      <motion.div
        className="h-full rounded-full"
        style={{
          background: `linear-gradient(90deg, ${C.primary}, ${C.secondary})`,
          boxShadow: `0 0 10px ${C.primary}`,
        }}
        initial={{ width: "0%" }}
        animate={{ width: "100%" }}
        transition={{ delay: 1.1, duration: (DURATION - 1600) / 1000, ease: [0.4, 0, 0.2, 1] }}
      />
    </motion.div>
  );
}
