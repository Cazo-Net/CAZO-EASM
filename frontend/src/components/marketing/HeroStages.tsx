"use client";

import { useRef } from "react";
import { motion, useScroll, useTransform } from "framer-motion";
import {
  Cloud,
  Server,
  Code,
  Shield,
  Network,
  Globe,
  Lock,
  Database,
  Cpu,
  Wifi,
  FileCode,
  AlertTriangle,
  CheckCircle2,
  GitBranch,
  Layers,
  ArrowRight,
} from "lucide-react";

/* ── Stage definitions ─────────────────────────────────────────────── */

interface Stage {
  id: number;
  label: string;
  tagline: string;
  description: string;
  icon: React.ElementType;
  color: string;
  gradient: string;
}

const STAGES: Stage[] = [
  {
    id: 4,
    label: "Cloud Discovery",
    tagline: "Map your cloud footprint",
    description:
      "Automatically detect AWS, GCP, Azure, and Cloudflare assets across your entire perimeter. Know which cloud providers host your exposed services.",
    icon: Cloud,
    color: "text-sky-400",
    gradient: "from-sky-500/20 to-cyan-500/10",
  },
  {
    id: 5,
    label: "Service Detection",
    tagline: "Fingerprint every service",
    description:
      "Identify web servers, databases, APIs, and custom applications. Wappalyzer-powered technology detection reveals your full stack.",
    icon: Server,
    color: "text-violet-400",
    gradient: "from-violet-500/20 to-purple-500/10",
  },
  {
    id: 6,
    label: "API Discovery",
    tagline: "Find hidden endpoints",
    description:
      "Discover REST, GraphQL, and gRPC endpoints that attackers target. Map your API surface before adversaries do.",
    icon: Code,
    color: "text-cyan-400",
    gradient: "from-cyan-500/20 to-blue-500/10",
  },
  {
    id: 7,
    label: "Risk Scoring",
    tagline: "Prioritize what matters",
    description:
      "Real-time risk scoring across your entire attack surface. CVE correlation, vulnerability severity, and exposure context in one score.",
    icon: Shield,
    color: "text-amber-400",
    gradient: "from-amber-500/20 to-orange-500/10",
  },
  {
    id: 8,
    label: "Relationships",
    tagline: "See the full picture",
    description:
      "Map IP-to-ASN relationships, shared hosting, registrar clustering, and certificate correlations. Understand how your assets connect.",
    icon: Network,
    color: "text-emerald-400",
    gradient: "from-emerald-500/20 to-green-500/10",
  },
];

/* ── Stage Visualizations ──────────────────────────────────────────── */

function CloudVisual() {
  const providers = [
    { name: "AWS", icon: Cloud, ips: ["52.14.89.103", "34.218.45.67"], count: 34 },
    { name: "Cloudflare", icon: Shield, ips: ["104.16.132.229"], count: 12 },
    { name: "GCP", icon: Server, ips: ["35.192.0.1"], count: 8 },
    { name: "Azure", icon: Database, ips: ["40.126.32.140"], count: 5 },
  ];
  return (
    <div className="grid grid-cols-2 gap-3">
      {providers.map((p, i) => (
        <motion.div
          key={p.name}
          initial={{ opacity: 0, scale: 0.9 }}
          whileInView={{ opacity: 1, scale: 1 }}
          transition={{ delay: i * 0.1, duration: 0.4 }}
          viewport={{ once: true }}
          className="rounded-xl border border-sky-500/20 bg-sky-500/5 p-4"
        >
          <div className="flex items-center gap-2 mb-2">
            <p.icon className="h-4 w-4 text-sky-400" />
            <span className="text-xs font-medium text-foreground">{p.name}</span>
            <span className="ml-auto text-[10px] text-sky-400">{p.count} assets</span>
          </div>
          {p.ips.map((ip) => (
            <div key={ip} className="font-mono text-[10px] text-muted-foreground">
              {ip}
            </div>
          ))}
        </motion.div>
      ))}
    </div>
  );
}

function ServiceVisual() {
  const services = [
    { name: "Nginx", version: "1.24.0", category: "Web Server", confidence: 98 },
    { name: "Node.js", version: "20.10", category: "Runtime", confidence: 95 },
    { name: "PostgreSQL", version: "16.1", category: "Database", confidence: 92 },
    { name: "Redis", version: "7.2.3", category: "Cache", confidence: 88 },
    { name: "React", version: "18.2", category: "Frontend", confidence: 96 },
    { name: "Express", version: "4.18", category: "Framework", confidence: 90 },
  ];
  return (
    <div className="space-y-2">
      {services.map((s, i) => (
        <motion.div
          key={s.name}
          initial={{ opacity: 0, x: -20 }}
          whileInView={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.08, duration: 0.3 }}
          viewport={{ once: true }}
          className="flex items-center gap-3 rounded-lg border border-violet-500/20 bg-violet-500/5 px-3 py-2"
        >
          <div className="h-2 w-2 rounded-full bg-violet-400" />
          <span className="text-xs font-medium text-foreground">{s.name}</span>
          <span className="text-[10px] text-muted-foreground">{s.version}</span>
          <span className="ml-auto text-[10px] text-violet-400">{s.confidence}%</span>
        </motion.div>
      ))}
    </div>
  );
}

function ApiVisual() {
  const endpoints = [
    { method: "GET", path: "/api/v2/users", status: 200, latency: "45ms" },
    { method: "POST", path: "/api/v2/auth/login", status: 200, latency: "120ms" },
    { method: "GET", path: "/api/internal/config", status: 403, latency: "12ms" },
    { method: "DELETE", path: "/api/v2/sessions/:id", status: 204, latency: "89ms" },
    { method: "PUT", path: "/graphql", status: 200, latency: "200ms" },
  ];
  const methodColors: Record<string, string> = {
    GET: "text-emerald-400 bg-emerald-500/10",
    POST: "text-amber-400 bg-amber-500/10",
    PUT: "text-cyan-400 bg-cyan-500/10",
    DELETE: "text-red-400 bg-red-500/10",
  };
  return (
    <div className="space-y-2">
      {endpoints.map((ep, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, x: -20 }}
          whileInView={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.08, duration: 0.3 }}
          viewport={{ once: true }}
          className="flex items-center gap-2 rounded-lg border border-cyan-500/20 bg-cyan-500/5 px-3 py-2"
        >
          <span
            className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
              methodColors[ep.method] || "text-gray-400 bg-gray-500/10"
            }`}
          >
            {ep.method}
          </span>
          <span className="font-mono text-[10px] text-foreground flex-1 truncate">
            {ep.path}
          </span>
          <span
            className={`text-[10px] ${
              ep.status < 300
                ? "text-emerald-400"
                : ep.status < 400
                ? "text-amber-400"
                : "text-red-400"
            }`}
          >
            {ep.status}
          </span>
        </motion.div>
      ))}
    </div>
  );
}

function RiskVisual() {
  const severities = [
    { label: "Critical", count: 2, color: "bg-red-500", pct: 8 },
    { label: "High", count: 5, color: "bg-orange-500", pct: 20 },
    { label: "Medium", count: 11, color: "bg-amber-500", pct: 44 },
    { label: "Low", count: 5, color: "bg-emerald-500", pct: 20 },
    { label: "Info", count: 2, color: "bg-sky-500", pct: 8 },
  ];
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <div className="relative h-20 w-20">
          <svg viewBox="0 0 36 36" className="h-full w-full -rotate-90">
            <circle
              cx="18"
              cy="18"
              r="16"
              fill="none"
              stroke="currentColor"
              strokeWidth="3"
              className="text-border/30"
            />
            <circle
              cx="18"
              cy="18"
              r="16"
              fill="none"
              stroke="currentColor"
              strokeWidth="3"
              strokeDasharray="100"
              strokeDashoffset="28"
              className="text-amber-400"
              strokeLinecap="round"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-lg font-bold text-foreground">72</span>
          </div>
        </div>
        <div className="flex-1 space-y-1.5">
          {severities.map((s) => (
            <div key={s.label} className="flex items-center gap-2">
              <div className={`h-1.5 w-1.5 rounded-full ${s.color}`} />
              <span className="text-[10px] text-muted-foreground w-12">{s.label}</span>
              <div className="flex-1 h-1.5 bg-border/30 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  whileInView={{ width: `${s.pct}%` }}
                  transition={{ duration: 0.6, delay: 0.2 }}
                  viewport={{ once: true }}
                  className={`h-full ${s.color} rounded-full`}
                />
              </div>
              <span className="text-[10px] text-foreground w-4 text-right">{s.count}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {[
          { label: "CVEs Found", value: "14", icon: AlertTriangle, color: "text-red-400" },
          { label: "Exposed Ports", value: "89", icon: Wifi, color: "text-cyan-400" },
          { label: "Cert Issues", value: "3", icon: Lock, color: "text-amber-400" },
        ].map((item) => (
          <div
            key={item.label}
            className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-2 text-center"
          >
            <item.icon className={`h-3.5 w-3.5 ${item.color} mx-auto mb-1`} />
            <p className="text-sm font-bold text-foreground">{item.value}</p>
            <p className="text-[9px] text-muted-foreground">{item.label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function RelationshipVisual() {
  const nodes = [
    { id: "root", label: "example.com", x: 50, y: 30, color: "bg-brand" },
    { id: "api", label: "api.example.com", x: 20, y: 55, color: "bg-cyan-400" },
    { id: "cdn", label: "cdn.example.com", x: 80, y: 55, color: "bg-violet-400" },
    { id: "auth", label: "auth.example.com", x: 35, y: 80, color: "bg-amber-400" },
    { id: "db", label: "db.example.com", x: 65, y: 80, color: "bg-red-400" },
  ];
  const edges = [
    { from: "root", to: "api" },
    { from: "root", to: "cdn" },
    { from: "api", to: "auth" },
    { from: "api", to: "db" },
    { from: "auth", to: "db" },
  ];
  return (
    <div className="relative h-48 w-full rounded-xl border border-emerald-500/20 bg-emerald-500/5 overflow-hidden">
      <svg className="absolute inset-0 h-full w-full">
        {edges.map((e, i) => {
          const from = nodes.find((n) => n.id === e.from)!;
          const to = nodes.find((n) => n.id === e.to)!;
          return (
            <motion.line
              key={i}
              x1={`${from.x}%`}
              y1={`${from.y}%`}
              x2={`${to.x}%`}
              y2={`${to.y}%`}
              stroke="rgba(52,211,153,0.3)"
              strokeWidth="1"
              initial={{ pathLength: 0, opacity: 0 }}
              whileInView={{ pathLength: 1, opacity: 1 }}
              transition={{ duration: 0.6, delay: i * 0.1 }}
              viewport={{ once: true }}
            />
          );
        })}
      </svg>
      {nodes.map((n, i) => (
        <motion.div
          key={n.id}
          initial={{ opacity: 0, scale: 0 }}
          whileInView={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3 + i * 0.1, type: "spring", stiffness: 200 }}
          viewport={{ once: true }}
          className="absolute -translate-x-1/2 -translate-y-1/2"
          style={{ left: `${n.x}%`, top: `${n.y}%` }}
        >
          <div
            className={`h-3 w-3 rounded-full ${n.color} ring-2 ring-background shadow-lg`}
          />
          <span className="absolute top-4 left-1/2 -translate-x-1/2 whitespace-nowrap text-[9px] text-muted-foreground font-mono">
            {n.label}
          </span>
        </motion.div>
      ))}
    </div>
  );
}

const STAGE_VISUALS: Record<number, React.FC> = {
  4: CloudVisual,
  5: ServiceVisual,
  6: ApiVisual,
  7: RiskVisual,
  8: RelationshipVisual,
};

/* ── Main Component ────────────────────────────────────────────────── */

export function HeroStages() {
  const containerRef = useRef<HTMLDivElement>(null);

  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"],
  });

  const stageIndex = useTransform(scrollYProgress, [0, 1], [0, STAGES.length - 1]);

  return (
    <div ref={containerRef} className="relative h-[400vh]">
      {/* Sticky stage container */}
      <div className="sticky top-0 h-screen flex items-center justify-center overflow-hidden">
        <div className="mx-auto max-w-6xl px-6 w-full">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            {/* Left: Stage info */}
            <div>
              <StagePills stageIndex={stageIndex} />
              <StageContent stageIndex={stageIndex} />
            </div>

            {/* Right: Stage visual */}
            <div className="hidden lg:block">
              <StageVisual stageIndex={stageIndex} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Sub-components ────────────────────────────────────────────────── */

function StagePillItem({ stageIndex, stage, index }: { stageIndex: any; stage: Stage; index: number }) {
  const fadeIn = Math.max(0.001, index - 0.3);
  const activeStart = index;
  const activeEnd = index + 0.7;
  const fadeOut = STAGES.length - 1;
  const opacity = useTransform(stageIndex, [fadeIn, activeStart, activeEnd, fadeOut], [0.3, 1, 1, 0.3]);
  const scale = useTransform(stageIndex, [fadeIn, activeStart, activeEnd, fadeOut], [0.95, 1, 1, 0.95]);

  return (
    <motion.div
      style={{ opacity, scale }}
      className="flex items-center gap-1.5 rounded-full border border-border/30 bg-card/50 px-3 py-1"
    >
      <stage.icon className={`h-3 w-3 ${stage.color}`} />
      <span className="text-[10px] text-muted-foreground">{stage.label}</span>
    </motion.div>
  );
}

function StagePills({ stageIndex }: { stageIndex: any }) {
  return (
    <div className="flex gap-2 mb-6">
      {STAGES.map((stage, i) => (
        <StagePillItem key={stage.id} stageIndex={stageIndex} stage={stage} index={i} />
      ))}
    </div>
  );
}

function StageContentItem({ stageIndex, stage, index }: { stageIndex: any; stage: Stage; index: number }) {
  const fadeIn = Math.max(0.001, index - 0.4);
  const activeStart = index;
  const activeEnd = index + 0.6;
  const fadeOut = STAGES.length - 1;
  const opacity = useTransform(stageIndex, [fadeIn, activeStart, activeEnd, fadeOut], [0, 1, 1, 0]);
  const y = useTransform(stageIndex, [fadeIn, activeStart, activeEnd, fadeOut], [30, 0, 0, -30]);

  return (
    <motion.div
      style={{ opacity, y }}
      className="absolute inset-0"
    >
      <div className="flex items-center gap-3 mb-3">
        <div
          className={`flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br ${stage.gradient}`}
        >
          <stage.icon className={`h-5 w-5 ${stage.color}`} />
        </div>
        <div>
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
            Stage {stage.id}
          </p>
          <h3 className="text-lg font-bold font-display text-foreground">{stage.tagline}</h3>
        </div>
      </div>
      <p className="text-sm text-muted-foreground leading-relaxed max-w-md">
        {stage.description}
      </p>
    </motion.div>
  );
}

function StageContent({ stageIndex }: { stageIndex: any }) {
  return (
    <div className="relative h-64">
      {STAGES.map((stage, i) => (
        <StageContentItem key={stage.id} stageIndex={stageIndex} stage={stage} index={i} />
      ))}
    </div>
  );
}

function StageVisualItem({ stageIndex, stage, index }: { stageIndex: any; stage: Stage; index: number }) {
  const fadeIn = Math.max(0.001, index - 0.4);
  const activeStart = index;
  const activeEnd = index + 0.6;
  const fadeOut = STAGES.length - 1;
  const opacity = useTransform(stageIndex, [fadeIn, activeStart, activeEnd, fadeOut], [0, 1, 1, 0]);
  const scale = useTransform(stageIndex, [fadeIn, activeStart, activeEnd, fadeOut], [0.95, 1, 1, 0.95]);

  const Visual = STAGE_VISUALS[stage.id];

  return (
    <motion.div
      style={{ opacity, scale }}
      className="absolute inset-0"
    >
      {Visual && <Visual />}
    </motion.div>
  );
}

function StageVisual({ stageIndex }: { stageIndex: any }) {
  return (
    <div className="relative h-80">
      {STAGES.map((stage, i) => (
        <StageVisualItem key={stage.id} stageIndex={stageIndex} stage={stage} index={i} />
      ))}
    </div>
  );
}
