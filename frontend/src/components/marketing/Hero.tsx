"use client";

/**
 * Landing hero. A static, readable first screen: what CAZO is, who it is
 * for, two actions, and a product view built from real UI patterns.
 * Replaces the scroll-driven HeroSequence, which left the first viewport
 * blank and hid the message behind ~8 screens of scrolling.
 */

import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Check,
  Globe,
  Server,
  ShieldAlert,
  Lock,
  Search,
  LayoutDashboard,
  Bug,
  Ghost,
  ScanSearch,
  FileText,
} from "lucide-react";
import { CazoMark } from "@/components/marketing/CazoLogo";

const EASE = [0.16, 1, 0.3, 1] as const;

export function Hero() {
  return (
    <section className="relative overflow-hidden">
      {/* Backdrop: faint grid + a single cool glow, no animation */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <div
          className="absolute inset-0 opacity-[0.35]"
          style={{
            backgroundImage:
              "linear-gradient(to right, rgb(255 255 255 / 0.04) 1px, transparent 1px), linear-gradient(to bottom, rgb(255 255 255 / 0.04) 1px, transparent 1px)",
            backgroundSize: "56px 56px",
            maskImage: "radial-gradient(ellipse 70% 60% at 50% 0%, #000 30%, transparent 75%)",
            WebkitMaskImage: "radial-gradient(ellipse 70% 60% at 50% 0%, #000 30%, transparent 75%)",
          }}
        />
        <div className="absolute left-1/2 top-[-280px] h-[560px] w-[1100px] -translate-x-1/2 rounded-full bg-primary/20 blur-[140px]" />
      </div>

      <div className="relative mx-auto max-w-6xl px-6 pb-20 pt-20 md:pt-28">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: EASE }}
          className="mx-auto max-w-3xl text-center"
        >
          <Link
            href="#how-it-works"
            className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] py-1 pl-1 pr-3 text-xs text-muted-foreground transition-colors hover:border-white/20 hover:text-foreground"
          >
            <span className="rounded-full bg-primary/15 px-2 py-0.5 font-medium text-primary">EASM</span>
            External attack surface management, with evidence
            <ArrowRight className="h-3 w-3" />
          </Link>

          <h1 className="mt-7 text-balance text-4xl font-semibold leading-[1.08] tracking-[-0.025em] text-white sm:text-5xl md:text-[64px]">
            You can&apos;t defend what you forgot you own.
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-balance text-base leading-relaxed text-slate-300/80 md:text-lg">
            CAZO continuously maps your internet-facing footprint — subdomains,
            open ports, certificates, services and misconfigurations — and shows
            the evidence behind every finding, so your team fixes what is real.
          </p>

          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href="/register"
              className="inline-flex h-11 items-center gap-2 rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground shadow-glow-sm transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-void"
            >
              Start a free scan <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="#product"
              className="inline-flex h-11 items-center gap-2 rounded-md border border-white/10 bg-white/[0.03] px-5 text-sm font-medium text-white transition-colors hover:bg-white/[0.07]"
            >
              See the product
            </Link>
          </div>

          <ul className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-[13px] text-slate-400">
            {["No agents to install", "Results in minutes", "Only assets you're authorized to scan"].map((t) => (
              <li key={t} className="inline-flex items-center gap-1.5">
                <Check className="h-3.5 w-3.5 text-primary" /> {t}
              </li>
            ))}
          </ul>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 28 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.15, ease: EASE }}
          className="relative mx-auto mt-16 max-w-5xl"
        >
          <ProductFrame />
        </motion.div>
      </div>
    </section>
  );
}

/* ── Product view (static, illustrative data) ─────────────────────── */

const SEV: Record<string, string> = {
  Critical: "bg-red-500/10 text-red-400 ring-red-500/30",
  High: "bg-orange-500/10 text-orange-400 ring-orange-500/30",
  Medium: "bg-amber-400/10 text-amber-300 ring-amber-400/30",
  Low: "bg-blue-500/10 text-blue-400 ring-blue-500/30",
};

const FINDINGS = [
  { sev: "Critical", title: "Exposed .env file with credentials", host: "staging.acme.com", age: "2h" },
  { sev: "High", title: "Jenkins dashboard reachable without auth", host: "ci.acme.com", age: "5h" },
  { sev: "High", title: "TLS certificate expires in 6 days", host: "vpn.acme.com", age: "1d" },
  { sev: "Medium", title: "Directory listing enabled", host: "cdn.acme.com", age: "1d" },
  { sev: "Low", title: "Server version disclosed in headers", host: "www.acme.com", age: "3d" },
];

function ProductFrame() {
  return (
    <div className="relative">
      <div aria-hidden="true" className="absolute -inset-px rounded-xl bg-gradient-to-b from-white/15 to-white/0" />
      <div
        className="relative overflow-hidden rounded-xl border border-white/10 bg-[#0E0E0E] shadow-[0_40px_120px_-30px_rgba(225,29,72,0.30)]"
        role="img"
        aria-label="CAZO dashboard showing asset counts and a list of findings sorted by severity"
      >
        {/* window bar */}
        <div className="flex h-10 items-center gap-3 border-b border-white/[0.06] bg-white/[0.02] px-4">
          <div className="flex gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-white/10" />
            <span className="h-2.5 w-2.5 rounded-full bg-white/10" />
            <span className="h-2.5 w-2.5 rounded-full bg-white/10" />
          </div>
          <div className="mx-auto flex h-6 w-72 max-w-[50%] items-center justify-center gap-1.5 rounded bg-white/[0.04] text-[11px] text-slate-500">
            <Lock className="h-3 w-3" /> app.cazoeasm.io/dashboard
          </div>
        </div>

        <div className="flex">
          {/* sidebar */}
          <div className="hidden w-48 shrink-0 border-r border-white/[0.06] p-3 md:block">
            <div className="mb-4 flex items-center gap-2 px-1.5">
              <CazoMark className="h-5 w-5" />
              <span className="text-[13px] font-semibold text-white">CAZO <span className="font-medium text-slate-400">EASM</span></span>
            </div>
            {[
              { i: LayoutDashboard, l: "Dashboard", a: true },
              { i: Globe, l: "Assets" },
              { i: Ghost, l: "Shadow assets" },
              { i: Bug, l: "Findings" },
              { i: ScanSearch, l: "Scans" },
              { i: FileText, l: "Reports" },
            ].map(({ i: I, l, a }) => (
              <div
                key={l}
                className={`mb-0.5 flex items-center gap-2 rounded-md px-2 py-1.5 text-[12px] ${
                  a ? "bg-primary/10 text-white" : "text-slate-400"
                }`}
              >
                <I className={`h-3.5 w-3.5 ${a ? "text-primary" : ""}`} /> {l}
              </div>
            ))}
          </div>

          {/* main */}
          <div className="min-w-0 flex-1 p-4 md:p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[15px] font-semibold text-white">acme.com</p>
                <p className="text-[11px] text-slate-500">Last scan 12 minutes ago · 4 stages complete</p>
              </div>
              <div className="hidden h-7 w-56 items-center gap-2 rounded-md border border-white/[0.08] bg-white/[0.02] px-2 text-[11px] text-slate-500 sm:flex">
                <Search className="h-3 w-3" /> Search assets, findings…
              </div>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
              {[
                { l: "Hosts", v: "318", i: Globe, d: "+12 this week" },
                { l: "Open ports", v: "1,204", i: Server, d: "+3 new" },
                { l: "Open findings", v: "47", i: ShieldAlert, d: "2 critical" },
                { l: "Certificates", v: "96", i: Lock, d: "2 expiring" },
              ].map(({ l, v, i: I, d }) => (
                <div key={l} className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-3">
                  <div className="flex items-center justify-between text-[11px] text-slate-400">
                    {l} <I className="h-3.5 w-3.5 text-slate-500" />
                  </div>
                  <p className="mt-1.5 text-xl font-semibold tabular-nums text-white">{v}</p>
                  <p className="text-[10px] text-slate-500">{d}</p>
                </div>
              ))}
            </div>

            <div className="mt-4 grid gap-3 lg:grid-cols-[1.6fr_1fr]">
              <div className="overflow-hidden rounded-lg border border-white/[0.07]">
                <div className="flex items-center justify-between border-b border-white/[0.06] bg-white/[0.02] px-3 py-2">
                  <span className="text-[12px] font-medium text-white">Top findings</span>
                  <span className="text-[10px] text-slate-500">sorted by severity</span>
                </div>
                {FINDINGS.map((f) => (
                  <div key={f.title} className="flex items-center gap-3 border-b border-white/[0.05] px-3 py-2 last:border-0">
                    <span className={`w-[58px] shrink-0 rounded px-1.5 py-0.5 text-center text-[10px] font-semibold ring-1 ring-inset ${SEV[f.sev]}`}>
                      {f.sev}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[12px] text-slate-200">{f.title}</p>
                      <p className="truncate font-mono text-[10px] text-slate-500">{f.host}</p>
                    </div>
                    <span className="text-[10px] text-slate-500">{f.age}</span>
                  </div>
                ))}
              </div>

              <div className="hidden rounded-lg border border-white/[0.07] p-3 lg:block">
                <p className="text-[12px] font-medium text-white">Findings by severity</p>
                <div className="mt-3 flex h-2 overflow-hidden rounded-full bg-white/[0.05]">
                  <div className="w-[4%] bg-red-500" />
                  <div className="w-[17%] bg-orange-500" />
                  <div className="w-[36%] bg-amber-400" />
                  <div className="w-[43%] bg-blue-500" />
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-[11px]">
                  {[
                    ["Critical", "2", "bg-red-500"],
                    ["High", "8", "bg-orange-500"],
                    ["Medium", "17", "bg-amber-400"],
                    ["Low", "20", "bg-blue-500"],
                  ].map(([l, v, c]) => (
                    <div key={l} className="flex items-center justify-between rounded border border-white/[0.05] px-2 py-1.5">
                      <span className="flex items-center gap-1.5 text-slate-400">
                        <span className={`h-1.5 w-1.5 rounded-sm ${c}`} /> {l}
                      </span>
                      <span className="font-medium tabular-nums text-white">{v}</span>
                    </div>
                  ))}
                </div>
                <div className="mt-3 rounded border border-white/[0.05] p-2">
                  <p className="text-[10px] text-slate-500">Evidence · staging.acme.com</p>
                  <p className="mt-1 font-mono text-[10px] leading-relaxed text-slate-300">
                    GET /.env → 200 OK<br />
                    DB_PASSWORD=<span className="rounded bg-white/10 px-1 text-slate-400">redacted</span>
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <p className="mt-3 text-center text-[11px] text-slate-500">Illustrative data</p>
    </div>
  );
}
