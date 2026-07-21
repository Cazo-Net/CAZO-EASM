"use client";

/**
 * HeroSequence — scroll-driven cascading hero for the CAZO landing page.
 *
 * Eight stages, unequal pacing (~860vh total), driven by real scroll position
 * (not autoplay) on both desktop and mobile. The final stage resolves into a
 * layout that resembles the real Attack Graph and then reveals a product
 * screenshot frame.
 *
 * Accessibility: when the user prefers reduced motion, the cascade collapses
 * into a single static, stacked summary of all stages (no scroll-jacking, no
 * transforms).
 *
 * Scroll source: because the app shell sets `overflow:hidden` on <body>, this
 * component reads scroll from an explicit container element passed via
 * `scrollContainerRef`. If none is provided it falls back to the window/viewport
 * (useful for isolated review of the component).
 */

import { useEffect, useRef, useState, type RefObject } from "react";
import {
  motion,
  useScroll,
  useTransform,
  useSpring,
  type MotionValue,
} from "framer-motion";
import {
  Globe,
  Building2,
  Network,
  Cloud,
  Server,
  Code2,
  ShieldAlert,
  GitBranch,
  ArrowDown,
} from "lucide-react";

/* ── Reduced-motion hook ───────────────────────────────────────────── */

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

/* ── Stage model + unequal pacing plan ─────────────────────────────── */

interface Stage {
  id: number;
  kicker: string;
  title: string;
  copy: string;
  icon: React.ElementType;
  accent: string; // tailwind text color
  ring: string; // tailwind border color
  /** relative scroll weight (vh) — denser stages get more room */
  vh: number;
}

const STAGES: Stage[] = [
  {
    id: 1,
    kicker: "The internet",
    title: "Billions of hosts. Most aren't yours.",
    copy: "Start from the open internet — the same vantage point an attacker has. No agents, no internal access.",
    icon: Globe,
    accent: "text-cyan-signal",
    ring: "border-cyan-signal/25",
    vh: 80,
  },
  {
    id: 2,
    kicker: "Your company",
    title: "We start from one thing you own.",
    copy: "A single domain is enough. CAZO resolves it to the organization behind it and works outward from there.",
    icon: Building2,
    accent: "text-phosphor",
    ring: "border-phosphor/25",
    vh: 80,
  },
  {
    id: 3,
    kicker: "Every domain",
    title: "Every subdomain, surfaced.",
    copy: "Passive sources, DNS brute-force, and permutation enumeration expand one domain into your full name footprint.",
    icon: Network,
    accent: "text-cyan-signal",
    ring: "border-cyan-signal/25",
    vh: 130,
  },
  {
    id: 4,
    kicker: "Every cloud",
    title: "Grouped by where it actually lives.",
    copy: "Assets are clustered by provider and network — AWS, GCP, Azure, Cloudflare — so you see your real hosting spread.",
    icon: Cloud,
    accent: "text-cyan-signal",
    ring: "border-cyan-signal/25",
    vh: 110,
  },
  {
    id: 5,
    kicker: "Every service",
    title: "Fingerprinted, port by port.",
    copy: "Open ports and banners reveal the web servers, runtimes, and stacks exposed on each host — with the evidence attached.",
    icon: Server,
    accent: "text-phosphor",
    ring: "border-phosphor/25",
    vh: 130,
  },
  {
    id: 6,
    kicker: "Every API",
    title: "The endpoints you forgot were public.",
    copy: "Reachable paths and interfaces are mapped so your API surface is visible before someone else maps it for you.",
    icon: Code2,
    accent: "text-cyan-signal",
    ring: "border-cyan-signal/25",
    vh: 110,
  },
  {
    id: 7,
    kicker: "Every risk",
    title: "Misconfigurations and known CVEs, correlated.",
    copy: "Exposed files, missing headers, weak TLS, and version-matched CVEs — each labeled with how sure we are, never overstated.",
    icon: ShieldAlert,
    accent: "text-signal-red",
    ring: "border-signal-red/25",
    vh: 120,
  },
  {
    id: 8,
    kicker: "Every relationship",
    title: "The whole surface, connected.",
    copy: "Shared IPs, certificates, and ASNs tie it together into one graph — the same view you'll work from inside CAZO.",
    icon: GitBranch,
    accent: "text-phosphor",
    ring: "border-phosphor/25",
    vh: 100,
  },
];

const TOTAL_VH = STAGES.reduce((sum, s) => sum + s.vh, 0); // ~860

/** Precompute normalized [start, end] scroll ranges for each stage. */
const RANGES = (() => {
  let acc = 0;
  return STAGES.map((s) => {
    const start = acc / TOTAL_VH;
    acc += s.vh;
    const end = acc / TOTAL_VH;
    return { start, end };
  });
})();

/* ── Per-stage active window helper ─────────────────────────────────── */

function useStageActivity(progress: MotionValue<number>, index: number) {
  const { start, end } = RANGES[index];
  const span = end - start;
  // fade in over first 30%, hold, fade out over last 30% of the stage window
  const inEnd = start + span * 0.3;
  const outStart = end - span * 0.3;
  const opacity = useTransform(
    progress,
    [start, inEnd, outStart, end],
    [0, 1, 1, 0],
  );
  const y = useTransform(
    progress,
    [start, inEnd, outStart, end],
    [40, 0, 0, -40],
  );
  return { opacity, y };
}

/* ── Stage text (left column) ──────────────────────────────────────── */

function StageText({
  progress,
  stage,
  index,
}: {
  progress: MotionValue<number>;
  stage: Stage;
  index: number;
}) {
  const { opacity, y } = useStageActivity(progress, index);
  const Icon = stage.icon;
  return (
    <motion.div style={{ opacity, y }} className="absolute inset-0">
      <div className="flex items-center gap-2 mb-4">
        <span
          className={`inline-flex h-8 w-8 items-center justify-center rounded-lg border ${stage.ring} bg-card/60`}
        >
          <Icon className={`h-4 w-4 ${stage.accent}`} />
        </span>
        <span
          className={`font-mono text-[11px] uppercase tracking-[0.18em] ${stage.accent}`}
        >
          {String(stage.id).padStart(2, "0")} · {stage.kicker}
        </span>
      </div>
      <h3 className="font-display text-2xl md:text-3xl font-semibold text-foreground leading-tight max-w-md">
        {stage.title}
      </h3>
      <p className="mt-3 text-sm md:text-base text-muted-foreground leading-relaxed max-w-md">
        {stage.copy}
      </p>
    </motion.div>
  );
}

/* ── Stage visuals (right column) ──────────────────────────────────── */

function StageVisualShell({
  progress,
  index,
  children,
}: {
  progress: MotionValue<number>;
  index: number;
  children: React.ReactNode;
}) {
  const { opacity } = useStageActivity(progress, index);
  const scale = useTransform(
    progress,
    [RANGES[index].start, RANGES[index].end],
    [0.97, 1.02],
  );
  return (
    <motion.div style={{ opacity, scale }} className="absolute inset-0">
      {children}
    </motion.div>
  );
}

/* Stage 1 — Internet: field of faint hosts with one about to light up */
function VisualInternet() {
  const dots = Array.from({ length: 48 });
  return (
    <div className="glass rounded-2xl h-full w-full p-6 grid grid-cols-8 gap-3 place-items-center overflow-hidden">
      {dots.map((_, i) => (
        <span
          key={i}
          className="h-1.5 w-1.5 rounded-full bg-muted-foreground/25"
          style={{ opacity: 0.2 + ((i * 7) % 10) / 20 }}
        />
      ))}
    </div>
  );
}

/* Stage 2 — Company: single resolving node */
function VisualCompany() {
  return (
    <div className="glass rounded-2xl h-full w-full flex flex-col items-center justify-center gap-4">
      <div className="relative">
        <span className="absolute inset-0 rounded-full bg-phosphor/20 blur-xl" />
        <span className="relative flex h-16 w-16 items-center justify-center rounded-2xl border border-phosphor/40 bg-phosphor/10">
          <Building2 className="h-7 w-7 text-phosphor" />
        </span>
      </div>
      <div className="text-center">
        <p className="font-mono text-sm text-foreground">acme.com</p>
        <p className="font-mono text-[11px] text-muted-foreground mt-1">
          resolved · 1 organization
        </p>
      </div>
    </div>
  );
}

/* Stage 3 — Domains: streaming subdomain list */
function VisualDomains() {
  const subs = [
    "api.acme.com",
    "staging.acme.com",
    "vpn.acme.com",
    "mail.acme.com",
    "assets.acme.com",
    "legacy.acme.com",
    "dev-7.acme.com",
    "status.acme.com",
    "admin.acme.com",
  ];
  return (
    <div className="glass rounded-2xl h-full w-full p-5 overflow-hidden">
      <p className="font-mono text-[11px] text-muted-foreground mb-3">
        discovered · {subs.length}+ hosts
      </p>
      <div className="space-y-1.5">
        {subs.map((s) => (
          <div
            key={s}
            className="flex items-center gap-2 rounded-md border border-cyan-signal/15 bg-cyan-signal/[0.04] px-2.5 py-1.5"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-cyan-signal" />
            <span className="font-mono text-[11px] text-foreground">{s}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* Stage 4 — Cloud: provider grouping */
function VisualCloud() {
  const providers = [
    { name: "AWS", n: 34 },
    { name: "Cloudflare", n: 12 },
    { name: "GCP", n: 8 },
    { name: "Azure", n: 5 },
  ];
  return (
    <div className="glass rounded-2xl h-full w-full p-5 grid grid-cols-2 gap-3 content-center">
      {providers.map((p) => (
        <div
          key={p.name}
          className="rounded-xl border border-cyan-signal/20 bg-cyan-signal/[0.04] p-4"
        >
          <div className="flex items-center gap-2">
            <Cloud className="h-4 w-4 text-cyan-signal" />
            <span className="text-xs font-medium text-foreground">
              {p.name}
            </span>
          </div>
          <p className="font-mono text-[11px] text-muted-foreground mt-2">
            {p.n} assets
          </p>
        </div>
      ))}
    </div>
  );
}

/* Stage 5 — Services: fingerprints with evidence */
function VisualServices() {
  const svcs = [
    { name: "nginx", ver: "1.24.0", port: 443 },
    { name: "OpenSSH", ver: "8.9p1", port: 22 },
    { name: "Node.js", ver: "18.0.0", port: 3000 },
    { name: "PostgreSQL", ver: "16.1", port: 5432 },
  ];
  return (
    <div className="glass rounded-2xl h-full w-full p-5 space-y-2 content-center">
      {svcs.map((s) => (
        <div
          key={s.name}
          className="flex items-center gap-3 rounded-lg border border-phosphor/15 bg-phosphor/[0.04] px-3 py-2"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-phosphor" />
          <span className="text-xs font-medium text-foreground w-24">
            {s.name}
          </span>
          <span className="font-mono text-[11px] text-muted-foreground">
            {s.ver}
          </span>
          <span className="ml-auto font-mono text-[11px] text-phosphor">
            :{s.port}
          </span>
        </div>
      ))}
    </div>
  );
}

/* Stage 6 — API: endpoints */
function VisualApi() {
  const eps = [
    { m: "GET", p: "/api/v2/users", s: 200 },
    { m: "POST", p: "/api/auth/login", s: 200 },
    { m: "GET", p: "/api/internal/config", s: 403 },
    { m: "GET", p: "/graphql", s: 200 },
  ];
  const mc: Record<string, string> = {
    GET: "text-phosphor bg-phosphor/10",
    POST: "text-amber bg-amber/10",
  };
  return (
    <div className="glass rounded-2xl h-full w-full p-5 space-y-2 content-center">
      {eps.map((e) => (
        <div
          key={e.p}
          className="flex items-center gap-2 rounded-lg border border-cyan-signal/15 bg-cyan-signal/[0.04] px-3 py-2"
        >
          <span
            className={`font-mono text-[10px] font-bold px-1.5 py-0.5 rounded ${
              mc[e.m] || "text-muted-foreground bg-muted/20"
            }`}
          >
            {e.m}
          </span>
          <span className="font-mono text-[11px] text-foreground flex-1 truncate">
            {e.p}
          </span>
          <span
            className={`font-mono text-[11px] ${
              e.s < 300 ? "text-phosphor" : "text-amber"
            }`}
          >
            {e.s}
          </span>
        </div>
      ))}
    </div>
  );
}

/* Stage 7 — Risk: findings — this hosts the single deliberate "live" pulse */
function VisualRisk() {
  const rows = [
    { sev: "CVE", label: "CVE-2026-21711 · Node.js 18.0.0", tone: "amber" },
    { sev: "HIGH", label: "Exposed .env file", tone: "red" },
    { sev: "MED", label: "Missing HSTS header", tone: "amber" },
    { sev: "LOW", label: "Directory listing enabled", tone: "cyan" },
  ];
  const tones: Record<string, string> = {
    red: "text-signal-red border-signal-red/25 bg-signal-red/[0.06]",
    amber: "text-amber border-amber/25 bg-amber/[0.06]",
    cyan: "text-cyan-signal border-cyan-signal/25 bg-cyan-signal/[0.06]",
  };
  return (
    <div className="glass rounded-2xl h-full w-full p-5 content-center space-y-2">
      <div className="flex items-center gap-2 mb-1">
        {/* the one deliberate live moment */}
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full rounded-full bg-phosphor/70 animate-ping-slow" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-phosphor" />
        </span>
        <span className="font-mono text-[11px] text-muted-foreground">
          scanning · live
        </span>
      </div>
      {rows.map((r) => (
        <div
          key={r.label}
          className={`flex items-center gap-3 rounded-lg border px-3 py-2 ${tones[r.tone]}`}
        >
          <span className="font-mono text-[10px] font-bold w-12">{r.sev}</span>
          <span className="font-mono text-[11px] text-foreground truncate">
            {r.label}
          </span>
        </div>
      ))}
    </div>
  );
}

/* Stage 8 — Relationships: mini attack-graph that resolves into a product frame */
function VisualGraph() {
  const nodes = [
    { id: "root", label: "acme.com", x: 50, y: 22, c: "bg-phosphor" },
    { id: "api", label: "api.acme.com", x: 22, y: 52, c: "bg-cyan-signal" },
    { id: "cdn", label: "cdn.acme.com", x: 78, y: 50, c: "bg-neon-violet" },
    { id: "auth", label: "auth.acme.com", x: 36, y: 82, c: "bg-amber" },
    { id: "db", label: "db.acme.com", x: 68, y: 80, c: "bg-signal-red" },
  ];
  const edges = [
    ["root", "api"],
    ["root", "cdn"],
    ["api", "auth"],
    ["api", "db"],
    ["auth", "db"],
  ];
  const at = (id: string) => nodes.find((n) => n.id === id)!;
  return (
    <div className="relative h-full w-full rounded-2xl border border-border/50 bg-void overflow-hidden">
      {/* product-frame chrome to hint this is the real Attack Graph */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border/40 bg-obsidian">
        <span className="h-2 w-2 rounded-full bg-signal-red/70" />
        <span className="h-2 w-2 rounded-full bg-amber/70" />
        <span className="h-2 w-2 rounded-full bg-phosphor/70" />
        <span className="ml-2 font-mono text-[10px] text-muted-foreground">
          cazo.io/graph
        </span>
      </div>
      <div className="relative h-[calc(100%-2.25rem)] w-full">
        <svg className="absolute inset-0 h-full w-full">
          {edges.map(([f, t], i) => (
            <line
              key={i}
              x1={`${at(f).x}%`}
              y1={`${at(f).y}%`}
              x2={`${at(t).x}%`}
              y2={`${at(t).y}%`}
              stroke="hsl(152 100% 50% / 0.25)"
              strokeWidth="1"
            />
          ))}
        </svg>
        {nodes.map((n) => (
          <div
            key={n.id}
            className="absolute -translate-x-1/2 -translate-y-1/2"
            style={{ left: `${n.x}%`, top: `${n.y}%` }}
          >
            <span
              className={`block h-3 w-3 rounded-full ${n.c} ring-2 ring-void shadow-glow-sm`}
            />
            <span className="absolute top-4 left-1/2 -translate-x-1/2 whitespace-nowrap font-mono text-[9px] text-muted-foreground">
              {n.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

const VISUALS: Record<number, React.FC> = {
  1: VisualInternet,
  2: VisualCompany,
  3: VisualDomains,
  4: VisualCloud,
  5: VisualServices,
  6: VisualApi,
  7: VisualRisk,
  8: VisualGraph,
};

/* ── Static (reduced-motion) fallback ──────────────────────────────── */

function StaticFallback() {
  return (
    <div className="mx-auto max-w-5xl px-6 py-16 space-y-6">
      {STAGES.map((s) => {
        const Icon = s.icon;
        const Visual = VISUALS[s.id];
        return (
          <div
            key={s.id}
            className="grid md:grid-cols-2 gap-6 items-center rounded-2xl border border-border/40 bg-card/40 p-6"
          >
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Icon className={`h-4 w-4 ${s.accent}`} />
                <span
                  className={`font-mono text-[11px] uppercase tracking-[0.18em] ${s.accent}`}
                >
                  {String(s.id).padStart(2, "0")} · {s.kicker}
                </span>
              </div>
              <h3 className="font-display text-xl font-semibold text-foreground">
                {s.title}
              </h3>
              <p className="mt-2 text-sm text-muted-foreground">{s.copy}</p>
            </div>
            <div className="h-56">{Visual && <Visual />}</div>
          </div>
        );
      })}
    </div>
  );
}

/* ── Main component ────────────────────────────────────────────────── */

export function HeroSequence({
  scrollContainerRef,
}: {
  scrollContainerRef?: RefObject<HTMLElement>;
}) {
  const reduced = usePrefersReducedMotion();
  const trackRef = useRef<HTMLDivElement>(null);

  const { scrollYProgress } = useScroll({
    target: trackRef,
    container: scrollContainerRef,
    offset: ["start start", "end end"],
  });

  // Smooth the raw scroll a touch so stage cross-fades don't feel jittery.
  const progress = useSpring(scrollYProgress, {
    stiffness: 120,
    damping: 30,
    mass: 0.3,
  });

  if (reduced) return <StaticFallback />;

  return (
    <div
      ref={trackRef}
      className="relative"
      style={{ height: `${TOTAL_VH}vh` }}
    >
      <div className="sticky top-0 h-screen flex items-center overflow-hidden">
        <div className="mx-auto w-full max-w-6xl px-6">
          <div
            data-hero-headline
            className="grid lg:grid-cols-2 gap-10 lg:gap-14 items-center"
          >
            {/* Left: stage copy (relative box holds absolutely-stacked stages) */}
            <div className="relative h-64 md:h-56">
              {STAGES.map((s, i) => (
                <StageText
                  key={s.id}
                  progress={progress}
                  stage={s}
                  index={i}
                />
              ))}
            </div>

            {/* Right: stage visuals */}
            <div className="relative h-72 md:h-80">
              {STAGES.map((s, i) => {
                const Visual = VISUALS[s.id];
                return (
                  <StageVisualShell key={s.id} progress={progress} index={i}>
                    {Visual && <Visual />}
                  </StageVisualShell>
                );
              })}
            </div>
          </div>

          {/* scroll affordance, fades after the first stage */}
          <ScrollHint progress={progress} />
        </div>
      </div>
    </div>
  );
}

function ScrollHint({ progress }: { progress: MotionValue<number> }) {
  const opacity = useTransform(progress, [0, 0.06], [1, 0]);
  return (
    <motion.div
      style={{ opacity }}
      className="pointer-events-none absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-1"
    >
      <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        scroll
      </span>
      <ArrowDown className="h-4 w-4 text-muted-foreground animate-bounce" />
    </motion.div>
  );
}
