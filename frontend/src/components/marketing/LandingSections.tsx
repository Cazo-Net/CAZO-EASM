"use client";

/**
 * Landing page content sections (below the hero).
 * Built one section at a time; each is a named export so the page can compose
 * them and reviewers can reason about them in isolation.
 *
 * Copy rules (per positioning): confident, technical, understated. No "AI",
 * no "revolutionize", no internet-wide/Shodan comparisons. Claims scoped to the
 * visitor's own organization footprint. All technical data uses mono type.
 */

import { useEffect, useRef, useState } from "react";
import {
  motion,
  AnimatePresence,
  useInView,
  useMotionValue,
  useTransform,
  animate,
} from "framer-motion";
import {
  FileSearch,
  Clock,
  Repeat2,
  CheckCircle2,
  ScanLine,
  Radar,
  GitMerge,
  ClipboardCheck,
  ArrowRight,
  Ghost,
  Fingerprint,
  Share2,
  Network,
  LayoutDashboard,
  Bug,
  Server,
  Lock,
  Globe,
  ShieldOff,
  Ban,
  Timer,
  XOctagon,
  Quote,
  ArrowUpRight,
  Shield,
  CreditCard,
  X,
  Minus,
  Plus,
  Layers,
  Boxes,
  Cpu,
} from "lucide-react";
import Link from "next/link";
import { CazoLogo } from "@/components/marketing/CazoLogo";

/* ── Shared section primitives ─────────────────────────────────────── */

const fadeUp = {
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] as const },
};

export function SectionKicker({ children }: { children: React.ReactNode }) {
  return (
    <span className="font-mono text-[11px] uppercase tracking-[0.22em] text-phosphor">
      {children}
    </span>
  );
}

/* ── Section 2 — Trust: "Every finding, with receipts" ─────────────── */

export function TrustSection() {
  return (
    <section
      id="trust"
      className="relative border-t border-border/40 bg-obsidian/40 py-24 md:py-32"
    >
      <div className="mx-auto max-w-6xl px-6">
        <div className="grid items-center gap-12 lg:grid-cols-2 lg:gap-16">
          {/* Copy */}
          <motion.div {...fadeUp}>
            <SectionKicker>Trust</SectionKicker>
            <h2 className="mt-4 font-display text-3xl font-semibold leading-tight text-foreground md:text-4xl">
              Every finding, with receipts.
            </h2>
            <p className="mt-5 max-w-md text-base leading-relaxed text-muted-foreground">
              A security tool you can&apos;t verify isn&apos;t one you can act
              on. Every asset CAZO reports shows how it was discovered, when it
              first appeared, and which scans have confirmed it since.
            </p>
            <p className="mt-4 max-w-md text-base leading-relaxed text-muted-foreground">
              No black-box scores. When you hand a finding to your team, the
              evidence comes with it.
            </p>

            <ul className="mt-8 space-y-3">
              {[
                "Discovery method for every asset — not just a list",
                "Timestamps you can trace back to a specific scan",
                "Confirmation history, so you know what's still live",
              ].map((item) => (
                <li key={item} className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-phosphor" />
                  <span className="text-sm text-muted-foreground">{item}</span>
                </li>
              ))}
            </ul>
          </motion.div>

          {/* Evidence Panel mockup */}
          <motion.div
            {...fadeUp}
            transition={{ ...fadeUp.transition, delay: 0.1 }}
          >
            <EvidencePanelMock />
          </motion.div>
        </div>
      </div>
    </section>
  );
}

/**
 * Realistic Evidence Panel — mirrors the product's provenance UI vocabulary
 * (discovery method, first seen, confirming scans, status).
 */
function EvidencePanelMock() {
  const rows: { icon: React.ElementType; label: string; value: React.ReactNode }[] =
    [
      {
        icon: FileSearch,
        label: "Discovery method",
        value: (
          <span className="text-foreground">
            crt.sh <span className="text-muted-foreground">·</span> DNS
            brute-force
          </span>
        ),
      },
      {
        icon: Clock,
        label: "First seen",
        value: (
          <span className="text-foreground">
            2026-02-14 14:03 UTC{" "}
            <span className="text-muted-foreground">(scan #0417)</span>
          </span>
        ),
      },
      {
        icon: Repeat2,
        label: "Confirming scans",
        value: (
          <span className="text-foreground">
            3 of 3 <span className="text-muted-foreground">· last 30d</span>
          </span>
        ),
      },
    ];

  return (
    <div className="relative">
      {/* soft depth glow */}
      <div className="absolute -inset-4 rounded-3xl bg-gradient-to-br from-phosphor/10 via-cyan-signal/5 to-transparent blur-2xl" />

      <div className="glass relative overflow-hidden rounded-2xl border border-border/60 shadow-elevation-3">
        {/* panel header */}
        <div className="flex items-center justify-between border-b border-border/50 bg-obsidian/60 px-4 py-3">
          <div className="flex items-center gap-2">
            <FileSearch className="h-4 w-4 text-phosphor" />
            <span className="text-sm font-medium text-foreground">
              Evidence
            </span>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-phosphor/30 bg-phosphor/10 px-2.5 py-1">
            <span className="h-1.5 w-1.5 rounded-full bg-phosphor" />
            <span className="font-mono text-[10px] uppercase tracking-wider text-phosphor">
              confirmed
            </span>
          </span>
        </div>

        {/* asset line */}
        <div className="border-b border-border/40 px-4 py-3">
          <p className="font-mono text-sm text-foreground">api.acme.com</p>
          <p className="mt-0.5 font-mono text-[11px] text-muted-foreground">
            A 52.14.89.103 · subdomain of acme.com
          </p>
        </div>

        {/* provenance rows */}
        <div className="divide-y divide-border/40">
          {rows.map((r) => {
            const Icon = r.icon;
            return (
              <div
                key={r.label}
                className="flex items-center gap-3 px-4 py-3.5"
              >
                <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
                <span className="w-36 shrink-0 text-xs text-muted-foreground">
                  {r.label}
                </span>
                <span className="font-mono text-[11px]">{r.value}</span>
              </div>
            );
          })}
        </div>

        {/* footer note — honesty cue */}
        <div className="border-t border-border/40 bg-obsidian/40 px-4 py-2.5">
          <p className="font-mono text-[10px] text-muted-foreground">
            every field above is traceable to a scan run — nothing inferred
          </p>
        </div>
      </div>
    </div>
  );
}

/* ── Metrics bar — capability facts (not fabricated customer counts) ── */

function CountUp({
  to,
  suffix = "",
  duration = 1.4,
}: {
  to: number;
  suffix?: string;
  duration?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const count = useMotionValue(0);
  const rounded = useTransform(count, (v) => Math.round(v).toLocaleString());

  useEffect(() => {
    if (!inView) return;
    const controls = animate(count, to, {
      duration,
      ease: [0.16, 1, 0.3, 1],
    });
    return () => controls.stop();
  }, [inView, to, duration, count]);

  return (
    <span ref={ref} className="tabular-nums">
      <motion.span>{rounded}</motion.span>
      {suffix}
    </span>
  );
}

const METRICS: {
  value: number;
  suffix: string;
  label: string;
  icon: React.ElementType;
}[] = [
  { value: 15, suffix: "+", label: "discovery sources per scan", icon: Layers },
  { value: 20, suffix: "+", label: "scanner modules", icon: Boxes },
  { value: 100, suffix: "%", label: "findings with evidence", icon: FileSearch },
  { value: 0, suffix: "", label: "agents to install", icon: Cpu },
];

export function MetricsBarSection() {
  return (
    <section className="relative border-y border-border/40 bg-obsidian/30 py-14">
      <div className="mx-auto max-w-6xl px-6">
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
          {METRICS.map((m, i) => {
            const Icon = m.icon;
            return (
              <motion.div
                key={m.label}
                {...fadeUp}
                transition={{ ...fadeUp.transition, delay: i * 0.08 }}
                className="flex flex-col items-center text-center"
              >
                <Icon className="mb-3 h-5 w-5 text-phosphor/70" />
                <p className="font-display text-3xl font-semibold text-foreground md:text-4xl">
                  <CountUp to={m.value} suffix={m.suffix} />
                </p>
                <p className="mt-1.5 max-w-[10rem] text-xs leading-snug text-muted-foreground">
                  {m.label}
                </p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

/* ── Section 3 — How it works ──────────────────────────────────────── */

const STEPS = [
  {
    n: "01",
    title: "Scan",
    icon: ScanLine,
    copy: "Enter one domain. No agents to install, no access to grant — CAZO works from the outside, the way an attacker would.",
    tag: "input: acme.com",
  },
  {
    n: "02",
    title: "Discover",
    icon: Radar,
    copy: "Subdomains, ports, certificates, and running services are enumerated across your perimeter and recorded with evidence.",
    tag: "hosts · ports · certs · tech",
  },
  {
    n: "03",
    title: "Correlate",
    icon: GitMerge,
    copy: "Shared IPs, certificates, and ASNs are matched against your known assets to surface what you may have forgotten you own.",
    tag: "shared IP · cert · ASN",
  },
  {
    n: "04",
    title: "Review",
    icon: ClipboardCheck,
    copy: "Work from a single graph of findings — each with provenance, freshness, and an honest status you can hand to your team.",
    tag: "findings · graph · status",
  },
] as const;

export function HowItWorksSection() {
  return (
    <section id="how-it-works" className="relative py-24 md:py-32">
      <div className="mx-auto max-w-6xl px-6">
        <motion.div {...fadeUp} className="max-w-2xl">
          <SectionKicker>How it works</SectionKicker>
          <h2 className="mt-4 font-display text-3xl font-semibold leading-tight text-foreground md:text-4xl">
            One domain in. Your whole external surface out.
          </h2>
          <p className="mt-4 text-base leading-relaxed text-muted-foreground">
            Four steps, no setup call. Start a scan and watch your footprint
            resolve.
          </p>
        </motion.div>

        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, i) => {
            const Icon = step.icon;
            return (
              <motion.div
                key={step.n}
                {...fadeUp}
                transition={{ ...fadeUp.transition, delay: i * 0.08 }}
                className="group relative"
              >
                {/* connector arrow between cards (desktop) */}
                {i < STEPS.length - 1 && (
                  <div className="pointer-events-none absolute -right-3 top-1/2 z-10 hidden -translate-y-1/2 lg:block">
                    <ArrowRight className="h-4 w-4 text-border" />
                  </div>
                )}

                <div className="glass h-full rounded-2xl border border-border/50 p-5 transition-colors duration-300 hover:border-phosphor/30">
                  <div className="flex items-center justify-between">
                    <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border/50 bg-obsidian/60">
                      <Icon className="h-4 w-4 text-phosphor" />
                    </span>
                    <span className="font-mono text-xs text-muted-foreground/60">
                      {step.n}
                    </span>
                  </div>

                  <h3 className="mt-4 font-display text-lg font-semibold text-foreground">
                    {step.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    {step.copy}
                  </p>

                  <div className="mt-4 border-t border-border/40 pt-3">
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {step.tag}
                    </span>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

/* ── Section 4 — Shadow Assets callout ─────────────────────────────── */

export function ShadowAssetsSection() {
  return (
    <section
      id="shadow-assets"
      className="relative overflow-hidden border-y border-border/40 py-28 md:py-36"
    >
      {/* atmospheric background — this section carries extra visual weight */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-1/4 top-0 h-72 w-72 -translate-x-1/2 rounded-full bg-signal-red/10 blur-[120px]" />
        <div className="absolute bottom-0 right-1/4 h-72 w-72 translate-x-1/2 rounded-full bg-neon-violet/10 blur-[120px]" />
      </div>

      <div className="relative mx-auto max-w-6xl px-6">
        <div className="grid items-center gap-14 lg:grid-cols-2 lg:gap-20">
          {/* Copy */}
          <motion.div {...fadeUp}>
            <div className="flex items-center gap-2">
              <Ghost className="h-4 w-4 text-signal-red" />
              <SectionKicker>
                <span className="text-signal-red">Shadow assets</span>
              </SectionKicker>
            </div>
            <h2 className="mt-4 font-display text-3xl font-semibold leading-[1.1] text-foreground md:text-5xl">
              What did you
              <br />
              forget you own?
            </h2>
            <p className="mt-6 max-w-md text-base leading-relaxed text-muted-foreground">
              The riskiest assets are the ones nobody remembers: a forgotten
              staging box, an old vendor subdomain, a certificate reused on
              infrastructure that isn&apos;t in your inventory.
            </p>
            <p className="mt-4 max-w-md text-base leading-relaxed text-muted-foreground">
              CAZO correlates shared infrastructure — IPs, certificates, and
              ASNs — against your confirmed assets to surface hosts that are
              probably yours, each with a confidence score and the exact reason
              it was flagged.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              {[
                { icon: Share2, label: "Shared IP" },
                { icon: Fingerprint, label: "Shared certificate" },
                { icon: Network, label: "Shared ASN" },
              ].map((s) => {
                const Icon = s.icon;
                return (
                  <span
                    key={s.label}
                    className="inline-flex items-center gap-2 rounded-full border border-border/50 bg-card/50 px-3 py-1.5"
                  >
                    <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="font-mono text-[11px] text-muted-foreground">
                      {s.label}
                    </span>
                  </span>
                );
              })}
            </div>
          </motion.div>

          {/* Flagged shadow-asset card */}
          <motion.div
            {...fadeUp}
            transition={{ ...fadeUp.transition, delay: 0.1 }}
          >
            <ShadowAssetCardMock />
          </motion.div>
        </div>
      </div>
    </section>
  );
}

/**
 * Realistic flagged shadow-asset card — mirrors the product's shadow-assets UI:
 * value + signal badges + "first seen" + confidence bar + explanatory reasons.
 */
function ShadowAssetCardMock() {
  const confidence = 82;
  const signals = [
    { label: "Shared Certificate", tone: "red" },
    { label: "Shared ASN (cloud)", tone: "muted" },
  ];
  const reasons = [
    {
      icon: Fingerprint,
      text: "Presents cert SHA-256 3f9a…c21b, also on 4 confirmed assets",
    },
    {
      icon: Network,
      text: "Hosted in AS13335 alongside cdn.acme.com, assets.acme.com",
    },
  ];
  const toneClass: Record<string, string> = {
    red: "border-signal-red/30 bg-signal-red/10 text-signal-red",
    muted: "border-border/50 bg-card/60 text-muted-foreground",
  };

  return (
    <div className="relative">
      <div className="absolute -inset-4 rounded-3xl bg-gradient-to-br from-signal-red/10 via-neon-violet/5 to-transparent blur-2xl" />

      <div className="glass relative overflow-hidden rounded-2xl border border-border/60 shadow-elevation-3">
        {/* header */}
        <div className="flex items-center justify-between border-b border-border/50 bg-obsidian/60 px-4 py-3">
          <div className="flex items-center gap-2">
            <Ghost className="h-4 w-4 text-signal-red" />
            <span className="text-sm font-medium text-foreground">
              Shadow asset candidate
            </span>
          </div>
          <span className="font-mono text-[10px] text-muted-foreground">
            unreviewed
          </span>
        </div>

        {/* asset + signals */}
        <div className="px-4 py-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm text-foreground">
              vendor-portal.acme-legacy.net
            </span>
            {signals.map((s) => (
              <span
                key={s.label}
                className={`rounded-md border px-2 py-0.5 font-mono text-[10px] ${toneClass[s.tone]}`}
              >
                {s.label}
              </span>
            ))}
          </div>
          <div className="mt-1.5 flex items-center gap-3">
            <span className="inline-flex items-center gap-1 font-mono text-[11px] text-muted-foreground">
              <Clock className="h-3 w-3" /> first seen 6 days ago
            </span>
            <span className="font-mono text-[11px] text-muted-foreground">
              2 shared-infra signals
            </span>
          </div>

          {/* confidence bar */}
          <div className="mt-4">
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-[11px] text-muted-foreground">
                Likelihood this is yours
              </span>
              <span className="font-mono text-xs font-semibold text-warning">
                {confidence}% confidence
              </span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary/60">
              <motion.div
                initial={{ width: 0 }}
                whileInView={{ width: `${confidence}%` }}
                viewport={{ once: true }}
                transition={{ duration: 0.8, ease: "easeOut", delay: 0.2 }}
                className="h-full rounded-full bg-warning"
              />
            </div>
          </div>
        </div>

        {/* why it was flagged */}
        <div className="border-t border-border/40 bg-obsidian/40 px-4 py-3">
          <p className="mb-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            why it was flagged
          </p>
          <ul className="space-y-2">
            {reasons.map((r) => {
              const Icon = r.icon;
              return (
                <li key={r.text} className="flex items-start gap-2">
                  <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  <span className="font-mono text-[11px] leading-relaxed text-muted-foreground">
                    {r.text}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </div>
  );
}

/* ── Section 5 — Product preview ───────────────────────────────────── */

type PreviewTab = "dashboard" | "vulnerabilities" | "graph";

const PREVIEW_TABS: { key: PreviewTab; label: string; icon: React.ElementType }[] =
  [
    { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
    { key: "vulnerabilities", label: "Vulnerabilities", icon: Bug },
    { key: "graph", label: "Attack Graph", icon: Network },
  ];

export function ProductPreviewSection() {
  const [tab, setTab] = useState<PreviewTab>("dashboard");

  return (
    <section
      id="product"
      className="relative border-t border-border/40 bg-obsidian/40 py-24 md:py-32"
    >
      <div className="mx-auto max-w-6xl px-6">
        <motion.div {...fadeUp} className="max-w-2xl">
          <SectionKicker>The product</SectionKicker>
          <h2 className="mt-4 font-display text-3xl font-semibold leading-tight text-foreground md:text-4xl">
            Not a report. A place to work.
          </h2>
          <p className="mt-4 text-base leading-relaxed text-muted-foreground">
            Your attack surface, your findings, and their history — in one
            interface built for people who&apos;ll actually act on it.
          </p>
        </motion.div>

        {/* tabs */}
        <div className="mt-10 flex flex-wrap gap-2">
          {PREVIEW_TABS.map((t) => {
            const Icon = t.icon;
            const active = tab === t.key;
            return (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`inline-flex items-center gap-2 rounded-lg border px-3.5 py-2 text-sm font-medium transition-colors ${
                  active
                    ? "border-phosphor/40 bg-phosphor/10 text-phosphor"
                    : "border-border/50 bg-card/40 text-muted-foreground hover:border-border hover:text-foreground"
                }`}
              >
                <Icon className="h-4 w-4" />
                {t.label}
              </button>
            );
          })}
        </div>

        {/* framed preview */}
        <motion.div {...fadeUp} className="relative mt-6">
          <div className="absolute -inset-4 rounded-3xl bg-gradient-to-r from-phosphor/10 via-cyan-signal/5 to-neon-violet/10 opacity-50 blur-2xl" />
          <div className="glass relative overflow-hidden rounded-2xl border border-border/60 shadow-elevation-3">
            {/* browser chrome */}
            <div className="flex items-center gap-2 border-b border-border/50 bg-void px-4 py-2.5">
              <span className="h-2.5 w-2.5 rounded-full bg-signal-red/70" />
              <span className="h-2.5 w-2.5 rounded-full bg-amber/70" />
              <span className="h-2.5 w-2.5 rounded-full bg-phosphor/70" />
              <div className="ml-3 flex flex-1 items-center gap-2 rounded-md border border-border/40 bg-obsidian/60 px-3 py-1">
                <Lock className="h-3 w-3 text-muted-foreground" />
                <span className="font-mono text-[11px] text-muted-foreground">
                  cazo.io/{tab === "graph" ? "graph" : tab}
                </span>
              </div>
            </div>

            {/*
              Screenshot slot: each mock below is a drop-in replacement point.
              To use a real screenshot, swap the <PreviewX /> for:
                <Image src="/preview-dashboard.png" ... className="w-full" />
            */}
            <div className="min-h-[360px] bg-void p-4 md:p-6">
              <AnimatePresence mode="wait">
                <motion.div
                  key={tab}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.25 }}
                >
                  {tab === "dashboard" && <PreviewDashboard />}
                  {tab === "vulnerabilities" && <PreviewVulnerabilities />}
                  {tab === "graph" && <PreviewGraph />}
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

function PreviewDashboard() {
  const stats = [
    { label: "Assets", value: "1,284", icon: Globe, accent: "text-cyan-signal" },
    { label: "Subdomains", value: "417", icon: Network, accent: "text-phosphor" },
    { label: "Open ports", value: "89", icon: Server, accent: "text-amber" },
    { label: "Findings", value: "23", icon: Bug, accent: "text-signal-red" },
  ];
  const recent = [
    { host: "api.acme.com", note: "new subdomain", tone: "text-phosphor" },
    { host: "staging.acme.com", note: "port 8080 opened", tone: "text-amber" },
    { host: "vpn.acme.com", note: "cert expires in 12d", tone: "text-signal-red" },
    { host: "cdn.acme.com", note: "tech changed: nginx 1.24", tone: "text-cyan-signal" },
  ];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {stats.map((s) => {
          const Icon = s.icon;
          return (
            <div
              key={s.label}
              className="rounded-xl border border-border/50 bg-card/40 p-4"
            >
              <div className="flex items-center justify-between">
                <Icon className={`h-4 w-4 ${s.accent}`} />
                <span className="h-1.5 w-1.5 rounded-full bg-phosphor/50" />
              </div>
              <p className="mt-3 font-display text-2xl font-semibold text-foreground">
                {s.value}
              </p>
              <p className="font-mono text-[11px] text-muted-foreground">
                {s.label}
              </p>
            </div>
          );
        })}
      </div>
      <div className="rounded-xl border border-border/50 bg-card/40 p-4">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-sm font-medium text-foreground">
            What&apos;s new since last scan
          </span>
          <span className="font-mono text-[10px] text-muted-foreground">
            scan #0417 · 2h ago
          </span>
        </div>
        <div className="space-y-2">
          {recent.map((r) => (
            <div
              key={r.host}
              className="flex items-center gap-3 rounded-lg border border-border/40 bg-obsidian/40 px-3 py-2"
            >
              <span className={`h-1.5 w-1.5 rounded-full ${r.tone.replace("text-", "bg-")}`} />
              <span className="font-mono text-[11px] text-foreground">
                {r.host}
              </span>
              <span className={`ml-auto font-mono text-[11px] ${r.tone}`}>
                {r.note}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function PreviewVulnerabilities() {
  const rows = [
    { sev: "critical", id: "misc/exposed-aws", host: "backup.acme.com", verified: true },
    { sev: "high", id: "misc/exposed-env", host: "dev-7.acme.com", verified: true },
    { sev: "medium", id: "cve/CVE-2026-21711", host: "api.acme.com", verified: false },
    { sev: "medium", id: "hdr/missing-hsts", host: "acme.com", verified: true },
    { sev: "low", id: "misc/dir-listing", host: "assets.acme.com", verified: true },
  ];
  const sevClass: Record<string, string> = {
    critical: "text-severity-critical bg-severity-critical/10 border-severity-critical/20",
    high: "text-severity-high bg-severity-high/10 border-severity-high/20",
    medium: "text-severity-medium bg-severity-medium/10 border-severity-medium/20",
    low: "text-severity-low bg-severity-low/10 border-severity-low/20",
  };
  return (
    <div className="rounded-xl border border-border/50 bg-card/40">
      <div className="flex items-center justify-between border-b border-border/40 px-4 py-3">
        <span className="text-sm font-medium text-foreground">Findings</span>
        <span className="font-mono text-[10px] text-muted-foreground">
          5 shown · sorted by severity
        </span>
      </div>
      <div className="divide-y divide-border/40">
        {rows.map((r) => (
          <div key={r.id} className="flex items-center gap-3 px-4 py-3">
            <span
              className={`w-16 rounded border px-1.5 py-0.5 text-center font-mono text-[10px] font-bold uppercase ${sevClass[r.sev]}`}
            >
              {r.sev}
            </span>
            <span className="font-mono text-[11px] text-foreground">{r.id}</span>
            <span className="font-mono text-[11px] text-muted-foreground">
              {r.host}
            </span>
            <span
              className={`ml-auto rounded px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider ${
                r.verified
                  ? "bg-phosphor/10 text-phosphor"
                  : "bg-amber/10 text-amber"
              }`}
              title={
                r.verified
                  ? "Directly observed by a scan"
                  : "Version-correlated against NVD — not exploit-verified"
              }
            >
              {r.verified ? "verified" : "unverified"}
            </span>
          </div>
        ))}
      </div>
      <div className="border-t border-border/40 px-4 py-2.5">
        <p className="font-mono text-[10px] text-muted-foreground">
          CVE matches are version-correlated and labeled{" "}
          <span className="text-amber">unverified</span> — never shown as
          confirmed exploits
        </p>
      </div>
    </div>
  );
}

function PreviewGraph() {
  const nodes = [
    { id: "root", label: "acme.com", x: 50, y: 18, c: "bg-phosphor" },
    { id: "api", label: "api.acme.com", x: 24, y: 46, c: "bg-cyan-signal" },
    { id: "cdn", label: "cdn.acme.com", x: 76, y: 44, c: "bg-neon-violet" },
    { id: "auth", label: "auth.acme.com", x: 32, y: 78, c: "bg-amber" },
    { id: "db", label: "db.acme.com", x: 60, y: 80, c: "bg-signal-red" },
    { id: "shadow", label: "vendor-portal.acme-legacy.net", x: 86, y: 74, c: "bg-signal-red" },
  ];
  const edges: [string, string][] = [
    ["root", "api"],
    ["root", "cdn"],
    ["api", "auth"],
    ["api", "db"],
    ["auth", "db"],
    ["cdn", "shadow"],
  ];
  const at = (id: string) => nodes.find((n) => n.id === id)!;
  return (
    <div className="relative h-[360px] w-full overflow-hidden rounded-xl border border-border/50 bg-void">
      <svg className="absolute inset-0 h-full w-full">
        {edges.map(([f, t], i) => {
          const shadow = t === "shadow";
          return (
            <line
              key={i}
              x1={`${at(f).x}%`}
              y1={`${at(f).y}%`}
              x2={`${at(t).x}%`}
              y2={`${at(t).y}%`}
              stroke={
                shadow ? "hsl(345 80% 60% / 0.4)" : "hsl(152 100% 50% / 0.22)"
              }
              strokeWidth="1"
              strokeDasharray={shadow ? "4 3" : undefined}
            />
          );
        })}
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
          <span className="absolute left-1/2 top-4 -translate-x-1/2 whitespace-nowrap font-mono text-[9px] text-muted-foreground">
            {n.label}
          </span>
        </div>
      ))}
      {/* legend */}
      <div className="absolute bottom-3 left-3 flex items-center gap-3 rounded-lg border border-border/40 bg-obsidian/70 px-3 py-1.5">
        <span className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-phosphor" />
          <span className="font-mono text-[9px] text-muted-foreground">
            confirmed
          </span>
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-signal-red" />
          <span className="font-mono text-[9px] text-muted-foreground">
            shadow candidate
          </span>
        </span>
      </div>
    </div>
  );
}

/* ── Section 6 — Honest reporting callout ──────────────────────────── */

const STATUS_ROWS = [
  {
    scanner: "port-scan",
    status: "ok",
    detail: "22, 80, 443 open",
    tone: "ok" as const,
  },
  {
    scanner: "subdomain-bruteforce",
    status: "ok",
    detail: "37 found",
    tone: "ok" as const,
  },
  {
    scanner: "tech-detect",
    status: "rate-limited",
    detail: "retried, partial result",
    tone: "warn" as const,
  },
  {
    scanner: "http-probe",
    status: "blocked-by-cdn",
    detail: "WAF returned 403",
    tone: "warn" as const,
  },
  {
    scanner: "whois",
    status: "error",
    detail: "registry timeout",
    tone: "err" as const,
  },
];

const TONE: Record<
  string,
  { badge: string; icon: React.ElementType; dot: string }
> = {
  ok: {
    badge: "border-phosphor/30 bg-phosphor/10 text-phosphor",
    icon: CheckCircle2,
    dot: "bg-phosphor",
  },
  warn: {
    badge: "border-warning/30 bg-warning/10 text-warning",
    icon: Timer,
    dot: "bg-warning",
  },
  err: {
    badge: "border-destructive/30 bg-destructive/10 text-destructive",
    icon: XOctagon,
    dot: "bg-destructive",
  },
};

export function HonestReportingSection() {
  return (
    <section id="honesty" className="relative py-24 md:py-32">
      <div className="mx-auto max-w-6xl px-6">
        <div className="grid items-center gap-14 lg:grid-cols-2 lg:gap-16">
          {/* status panel — placed first on desktop for emphasis */}
          <motion.div {...fadeUp} className="order-2 lg:order-1">
            <div className="relative">
              <div className="absolute -inset-4 rounded-3xl bg-gradient-to-br from-warning/10 via-transparent to-transparent blur-2xl" />
              <div className="glass relative overflow-hidden rounded-2xl border border-border/60 shadow-elevation-3">
                <div className="flex items-center justify-between border-b border-border/50 bg-obsidian/60 px-4 py-3">
                  <span className="text-sm font-medium text-foreground">
                    Scanner status
                  </span>
                  <span className="font-mono text-[10px] text-muted-foreground">
                    scan #0417
                  </span>
                </div>
                <div className="divide-y divide-border/40">
                  {STATUS_ROWS.map((r) => {
                    const t = TONE[r.tone];
                    const Icon = t.icon;
                    return (
                      <div
                        key={r.scanner}
                        className="flex items-center gap-3 px-4 py-3"
                      >
                        <span className={`h-1.5 w-1.5 rounded-full ${t.dot}`} />
                        <span className="font-mono text-[11px] text-foreground w-44 shrink-0">
                          {r.scanner}
                        </span>
                        <span
                          className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[10px] ${t.badge}`}
                        >
                          <Icon className="h-3 w-3" />
                          {r.status}
                        </span>
                        <span className="ml-auto hidden font-mono text-[10px] text-muted-foreground sm:block">
                          {r.detail}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <div className="border-t border-border/40 bg-obsidian/40 px-4 py-2.5">
                  <p className="font-mono text-[10px] text-muted-foreground">
                    3 ok · 2 need attention — no result is silently dropped
                  </p>
                </div>
              </div>
            </div>
          </motion.div>

          {/* copy */}
          <motion.div
            {...fadeUp}
            transition={{ ...fadeUp.transition, delay: 0.1 }}
            className="order-1 lg:order-2"
          >
            <div className="flex items-center gap-2">
              <ShieldOff className="h-4 w-4 text-warning" />
              <SectionKicker>
                <span className="text-warning">Honest reporting</span>
              </SectionKicker>
            </div>
            <h2 className="mt-4 font-display text-3xl font-semibold leading-tight text-foreground md:text-4xl">
              A <span className="font-mono text-2xl md:text-3xl">0</span> should
              mean clean — not broken.
            </h2>
            <p className="mt-5 max-w-md text-base leading-relaxed text-muted-foreground">
              Most scanners collapse &quot;we found nothing&quot; and &quot;we
              couldn&apos;t check&quot; into the same empty result. That&apos;s
              how real exposure hides in plain sight.
            </p>
            <p className="mt-4 max-w-md text-base leading-relaxed text-muted-foreground">
              CAZO reports the state of every scanner. If a host was
              rate-limited, blocked by a CDN, or the check errored out,
              you&apos;ll see it — clearly labeled, never disguised as a clean
              result.
            </p>

            <div className="mt-8 flex flex-wrap gap-2">
              {[
                { icon: CheckCircle2, label: "ok", tone: "ok" },
                { icon: Timer, label: "rate-limited", tone: "warn" },
                { icon: Ban, label: "blocked-by-cdn", tone: "warn" },
                { icon: XOctagon, label: "error", tone: "err" },
              ].map((b) => {
                const t = TONE[b.tone];
                const Icon = b.icon;
                return (
                  <span
                    key={b.label}
                    className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 font-mono text-[11px] ${t.badge}`}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {b.label}
                  </span>
                );
              })}
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

/* ── Section 7 — Social proof (placeholder-ready) ──────────────────────
 *
 * Structure only. Populate these arrays with real content when available;
 * the section renders honest placeholder states while they are empty and
 * never fabricates logos or testimonials.
 */

interface Logo {
  name: string;
  src: string; // path under /public
}
interface Testimonial {
  quote: string;
  name: string;
  role: string;
  company: string;
}

export const CUSTOMER_LOGOS: Logo[] = [];
export const TESTIMONIALS: Testimonial[] = [];

export function SocialProofSection() {
  const hasLogos = CUSTOMER_LOGOS.length > 0;
  const hasTestimonials = TESTIMONIALS.length > 0;

  return (
    <section
      id="proof"
      className="relative border-t border-border/40 bg-obsidian/40 py-24 md:py-28"
    >
      <div className="mx-auto max-w-6xl px-6">
        <motion.div {...fadeUp} className="text-center">
          <SectionKicker>Who&apos;s using CAZO</SectionKicker>
          <h2 className="mx-auto mt-4 max-w-2xl font-display text-2xl font-semibold leading-tight text-foreground md:text-3xl">
            Built for teams who own their perimeter.
          </h2>
        </motion.div>

        {/* Logo strip */}
        <motion.div {...fadeUp} className="mt-12">
          {hasLogos ? (
            <div className="flex flex-wrap items-center justify-center gap-x-12 gap-y-8 opacity-70">
              {CUSTOMER_LOGOS.map((logo) => (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  key={logo.name}
                  src={logo.src}
                  alt={logo.name}
                  className="h-7 w-auto grayscale transition hover:grayscale-0"
                />
              ))}
            </div>
          ) : (
            <div className="flex flex-wrap items-center justify-center gap-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <div
                  key={i}
                  className="flex h-11 w-32 items-center justify-center rounded-lg border border-dashed border-border/50 bg-card/20"
                >
                  <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground/50">
                    your logo
                  </span>
                </div>
              ))}
            </div>
          )}
        </motion.div>

        {/* Testimonials */}
        <div className="mt-14 grid gap-4 md:grid-cols-3">
          {hasTestimonials
            ? TESTIMONIALS.map((t) => (
                <motion.figure
                  key={t.name}
                  {...fadeUp}
                  className="glass rounded-2xl border border-border/50 p-6"
                >
                  <Quote className="h-5 w-5 text-phosphor/60" />
                  <blockquote className="mt-3 text-sm leading-relaxed text-foreground">
                    {t.quote}
                  </blockquote>
                  <figcaption className="mt-4 border-t border-border/40 pt-4">
                    <p className="text-sm font-medium text-foreground">
                      {t.name}
                    </p>
                    <p className="font-mono text-[11px] text-muted-foreground">
                      {t.role} · {t.company}
                    </p>
                  </figcaption>
                </motion.figure>
              ))
            : Array.from({ length: 3 }).map((_, i) => (
                <motion.div
                  key={i}
                  {...fadeUp}
                  transition={{ ...fadeUp.transition, delay: i * 0.08 }}
                  className="rounded-2xl border border-dashed border-border/50 bg-card/20 p-6"
                >
                  <Quote className="h-5 w-5 text-muted-foreground/30" />
                  <div className="mt-4 space-y-2">
                    <div className="h-2.5 w-full rounded bg-border/40" />
                    <div className="h-2.5 w-5/6 rounded bg-border/40" />
                    <div className="h-2.5 w-2/3 rounded bg-border/40" />
                  </div>
                  <div className="mt-5 border-t border-border/40 pt-4">
                    <p className="font-mono text-[11px] text-muted-foreground/60">
                      early-access customer
                    </p>
                  </div>
                </motion.div>
              ))}
        </div>

        {/* Honest note while empty */}
        {!hasTestimonials && (
          <motion.p
            {...fadeUp}
            className="mt-10 text-center text-sm text-muted-foreground"
          >
            CAZO is early. We&apos;d rather leave this space empty than fill it
            with names that aren&apos;t real yet.{" "}
            <a
              href="/register"
              className="inline-flex items-center gap-1 text-phosphor hover:underline"
            >
              Be one of the first
              <ArrowUpRight className="h-3.5 w-3.5" />
            </a>
          </motion.p>
        )}
      </div>
    </section>
  );
}

/* ── Comparison — CAZO vs a typical scanner ───────────────────────── */

const COMPARE_ROWS: {
  label: string;
  cazo: string;
  typical: string;
  typicalTone: "bad" | "meh";
}[] = [
  {
    label: "Evidence per finding",
    cazo: "Discovery method, timestamp & confirming scans",
    typical: "A score you have to trust",
    typicalTone: "bad",
  },
  {
    label: "Shadow assets",
    cazo: "Correlated via shared IP, cert & ASN",
    typical: "Only what you already listed",
    typicalTone: "bad",
  },
  {
    label: "Failed checks",
    cazo: "Reported as blocked / rate-limited / error",
    typical: "Silently shown as a clean 0",
    typicalTone: "bad",
  },
  {
    label: "CVE matches",
    cazo: "Labeled verified vs. version-correlated",
    typical: "Listed as confirmed exploits",
    typicalTone: "bad",
  },
  {
    label: "Setup",
    cazo: "One domain, no agents",
    typical: "Agents, access grants, onboarding call",
    typicalTone: "meh",
  },
];

export function ComparisonSection() {
  return (
    <section
      id="comparison"
      className="relative border-t border-border/40 py-24 md:py-32"
    >
      <div className="mx-auto max-w-5xl px-6">
        <motion.div {...fadeUp} className="mx-auto max-w-2xl text-center">
          <SectionKicker>The difference</SectionKicker>
          <h2 className="mt-4 font-display text-3xl font-semibold leading-tight text-foreground md:text-4xl">
            Most scanners tell you what. CAZO shows you why.
          </h2>
        </motion.div>

        <motion.div
          {...fadeUp}
          className="glass mt-12 overflow-hidden rounded-2xl border border-border/60 shadow-elevation-3"
        >
          {/* header row */}
          <div className="grid grid-cols-[1fr_1.2fr_1.2fr] border-b border-border/50 bg-obsidian/60">
            <div className="px-4 py-3.5" />
            <div className="flex items-center gap-2 border-l border-border/40 px-4 py-3.5">
              <CazoLogo />
            </div>
            <div className="border-l border-border/40 px-4 py-3.5">
              <span className="text-sm font-medium text-muted-foreground">
                Typical scanner
              </span>
            </div>
          </div>

          <div className="divide-y divide-border/40">
            {COMPARE_ROWS.map((r) => (
              <div
                key={r.label}
                className="grid grid-cols-[1fr_1.2fr_1.2fr] items-stretch"
              >
                <div className="flex items-center px-4 py-4">
                  <span className="text-xs font-medium text-muted-foreground">
                    {r.label}
                  </span>
                </div>
                <div className="flex items-start gap-2 border-l border-border/40 bg-phosphor/[0.03] px-4 py-4">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-phosphor" />
                  <span className="text-sm text-foreground">{r.cazo}</span>
                </div>
                <div className="flex items-start gap-2 border-l border-border/40 px-4 py-4">
                  {r.typicalTone === "bad" ? (
                    <X className="mt-0.5 h-4 w-4 shrink-0 text-signal-red/70" />
                  ) : (
                    <Minus className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground/60" />
                  )}
                  <span className="text-sm text-muted-foreground">
                    {r.typical}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  );
}

/* ── FAQ — reduce signup friction ──────────────────────────────────── */

const FAQS: { q: string; a: string }[] = [
  {
    q: "Do I need to install anything?",
    a: "No. CAZO works entirely from the outside — the same vantage point an attacker has. You give it one domain; there are no agents, no VPNs, and no access grants required.",
  },
  {
    q: "What can I scan?",
    a: "Only domains you own or are explicitly authorized to test. CAZO is built for defending your own perimeter, not probing third parties. You confirm authorization before a scan runs.",
  },
  {
    q: "How is this different from a vulnerability scanner?",
    a: "A scanner checks a list you give it. CAZO discovers the list first — subdomains, cloud footprint, services, and forgotten assets correlated by shared infrastructure — then attaches evidence to everything it finds.",
  },
  {
    q: "Do you show fake or inflated results?",
    a: "No. Every finding is traceable to a scan run. When a check is blocked, rate-limited, or errors out, we say so — we never disguise \u201ccouldn\u2019t check\u201d as \u201cclean.\u201d CVE matches are labeled version-correlated, not confirmed exploits.",
  },
  {
    q: "How long does a scan take?",
    a: "A first scan of a typical domain completes in a few minutes. Larger footprints take longer; you can keep working while it runs and results stream in as they resolve.",
  },
  {
    q: "Is there a free option?",
    a: "Yes. You can start a free scan with no credit card to see your external attack surface before deciding anything.",
  },
];

function FaqItem({
  q,
  a,
  isOpen,
  onToggle,
}: {
  q: string;
  a: string;
  isOpen: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="border-b border-border/40">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-4 py-5 text-left"
        aria-expanded={isOpen}
      >
        <span className="text-base font-medium text-foreground">{q}</span>
        <span className="relative flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border/50">
          <motion.span
            animate={{ rotate: isOpen ? 45 : 0 }}
            transition={{ duration: 0.2 }}
          >
            {isOpen ? (
              <Minus className="h-3.5 w-3.5 text-phosphor" />
            ) : (
              <Plus className="h-3.5 w-3.5 text-muted-foreground" />
            )}
          </motion.span>
        </span>
      </button>
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <p className="pb-5 pr-10 text-sm leading-relaxed text-muted-foreground">
              {a}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function FaqSection() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <section
      id="faq"
      className="relative border-t border-border/40 bg-obsidian/40 py-24 md:py-32"
    >
      <div className="mx-auto max-w-3xl px-6">
        <motion.div {...fadeUp} className="text-center">
          <SectionKicker>Questions</SectionKicker>
          <h2 className="mt-4 font-display text-3xl font-semibold leading-tight text-foreground md:text-4xl">
            Answers before you sign up.
          </h2>
        </motion.div>

        <motion.div {...fadeUp} className="mt-12">
          {FAQS.map((f, i) => (
            <FaqItem
              key={f.q}
              q={f.q}
              a={f.a}
              isOpen={open === i}
              onToggle={() => setOpen(open === i ? null : i)}
            />
          ))}
        </motion.div>

        <motion.p {...fadeUp} className="mt-10 text-center text-sm text-muted-foreground">
          Still curious?{" "}
          <a
            href="mailto:hello@cazo.io"
            className="inline-flex items-center gap-1 text-phosphor hover:underline"
          >
            Ask us anything
            <ArrowUpRight className="h-3.5 w-3.5" />
          </a>
        </motion.p>
      </div>
    </section>
  );
}

/* ── Section 8 — Final CTA ─────────────────────────────────────────── */

export function FinalCtaSection() {
  return (
    <section className="relative overflow-hidden py-28 md:py-36">
      {/* backdrop glow */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-1/2 top-1/2 h-96 w-[36rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-phosphor/10 blur-[140px]" />
      </div>

      <motion.div
        {...fadeUp}
        className="relative mx-auto max-w-3xl px-6 text-center"
      >
        <h2 className="font-display text-3xl font-semibold leading-[1.1] text-foreground md:text-5xl">
          See what you&apos;re exposing.
        </h2>
        <p className="mx-auto mt-5 max-w-xl text-base leading-relaxed text-muted-foreground">
          Point CAZO at one domain and get a mapped, evidence-backed view of your
          external attack surface — including the assets you forgot you own.
        </p>

        <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link
            href="/register"
            className="group relative inline-flex items-center gap-2 overflow-hidden rounded-xl bg-phosphor px-6 py-3.5 text-sm font-semibold text-void shadow-glow-md transition hover:shadow-glow-lg hover:-translate-y-0.5"
          >
            <span className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/30 to-transparent transition-transform duration-700 group-hover:translate-x-full" />
            <span className="relative">Start free scan</span>
            <ArrowRight className="relative h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
          <Link
            href="/login"
            className="inline-flex items-center gap-2 rounded-xl border border-border/60 bg-card/40 px-6 py-3.5 text-sm font-medium text-foreground transition hover:border-border"
          >
            Log in
          </Link>
        </div>

        <div className="mt-6 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 font-mono text-[11px] text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <CreditCard className="h-3.5 w-3.5" /> no credit card
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Timer className="h-3.5 w-3.5" /> ~2 minutes
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Shield className="h-3.5 w-3.5" /> scan only what you&apos;re
            authorized to
          </span>
        </div>
      </motion.div>
    </section>
  );
}

/* ── Sticky nav ────────────────────────────────────────────────────── */

const NAV_LINKS = [
  { href: "#trust", label: "Trust" },
  { href: "#how-it-works", label: "How it works" },
  { href: "#shadow-assets", label: "Shadow assets" },
  { href: "#product", label: "Product" },
  { href: "#faq", label: "FAQ" },
];

export function LandingNav({
  scrolled,
  progress,
}: {
  scrolled?: boolean;
  progress?: number;
}) {
  return (
    <header
      className={`sticky top-0 z-50 transition-colors duration-300 ${
        scrolled
          ? "border-b border-border/50 bg-void/80 backdrop-blur-xl"
          : "border-b border-transparent"
      }`}
    >
      {/* scroll progress bar */}
      <div
        className="absolute inset-x-0 top-0 h-0.5 origin-left bg-gradient-to-r from-phosphor to-cyan-signal transition-transform duration-150 ease-out"
        style={{ transform: `scaleX(${progress ?? 0})` }}
      />
      <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <CazoLogo />

        <div className="hidden items-center gap-7 md:flex">
          {NAV_LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              {l.label}
            </a>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/login"
            className="hidden rounded-lg px-3.5 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground sm:inline-flex"
          >
            Log in
          </Link>
          <Link
            href="/register"
            className="inline-flex items-center gap-1.5 rounded-lg bg-phosphor px-3.5 py-2 text-sm font-semibold text-void shadow-glow-sm transition hover:shadow-glow-md"
          >
            Start free scan
          </Link>
        </div>
      </nav>
    </header>
  );
}

/* ── Section 9 — Footer ────────────────────────────────────────────── */

const FOOTER_COLS: { title: string; links: { label: string; href: string }[] }[] =
  [
    {
      title: "Product",
      links: [
        { label: "How it works", href: "#how-it-works" },
        { label: "Shadow assets", href: "#shadow-assets" },
        { label: "Product", href: "#product" },
        { label: "Start free scan", href: "/register" },
      ],
    },
    {
      title: "Company",
      links: [
        { label: "About", href: "/about" },
        { label: "Contact", href: "mailto:hello@cazo.io" },
      ],
    },
    {
      title: "Legal",
      links: [
        { label: "Terms of Service", href: "/legal/terms" },
        { label: "Authorized Scanning", href: "/legal/authorized-scanning" },
        { label: "Privacy Policy", href: "/legal/privacy" },
        { label: "Acceptable Use", href: "/legal/acceptable-use" },
      ],
    },
  ];

export function LandingFooter() {
  return (
    <footer className="border-t border-border/40 bg-void">
      <div className="mx-auto max-w-6xl px-6 py-14">
        <div className="grid gap-10 md:grid-cols-[1.5fr_1fr_1fr_1fr]">
          <div>
            <CazoLogo />
            <p className="mt-3 max-w-xs text-sm text-muted-foreground">
              External attack surface management with evidence behind every
              finding.
            </p>
          </div>

          {FOOTER_COLS.map((col) => (
            <div key={col.title}>
              <p className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground/70">
                {col.title}
              </p>
              <ul className="mt-4 space-y-2.5">
                {col.links.map((l) => (
                  <li key={l.label}>
                    <a
                      href={l.href}
                      className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                    >
                      {l.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col items-center justify-between gap-3 border-t border-border/40 pt-6 sm:flex-row">
          <p className="font-mono text-[11px] text-muted-foreground/70">
            © {new Date().getFullYear()} CAZO · cazo.io
          </p>
          <p className="font-mono text-[11px] text-muted-foreground/70">
            Scan only assets you own or are authorized to test.
          </p>
        </div>
      </div>
    </footer>
  );
}
