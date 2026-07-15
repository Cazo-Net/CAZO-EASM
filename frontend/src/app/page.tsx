"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion, useScroll, useTransform, useInView, AnimatePresence } from "framer-motion";
import {
  Shield,
  ArrowRight,
  Globe,
  Lock,
  Radar,
  Zap,
  Server,
  Bug,
  Search,
  BarChart3,
  Activity,
  Network,
  Target,
  Eye,
  ChevronRight,
  ChevronDown,
  Check,
  Star,
  Building2,
  FileText,
  Bell,
  Key,
  Code,
  Cloud,
  Users,
  Briefcase,
  AlertTriangle,
  CheckCircle2,
  Play,
  Scan,
  Webhook,
  MessageSquare,
  Github,
  Gitlab,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

/* ─── Animated Counter ─── */
function AnimatedCounter({ target, suffix = "", duration = 2 }: { target: number; suffix?: string; duration?: number }) {
  const [count, setCount] = useState(0);
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true });

  useEffect(() => {
    if (!isInView) return;
    let start = 0;
    const increment = target / (duration * 60);
    const timer = setInterval(() => {
      start += increment;
      if (start >= target) {
        setCount(target);
        clearInterval(timer);
      } else {
        setCount(Math.floor(start));
      }
    }, 1000 / 60);
    return () => clearInterval(timer);
  }, [isInView, target, duration]);

  return (
    <span ref={ref}>
      {count.toLocaleString()}{suffix}
    </span>
  );
}

/* ─── Network Animation ─── */
function NetworkAnimation() {
  const [nodes, setNodes] = useState<{ x: number; y: number; size: number; opacity: number; pulse: boolean; color: string }[]>([]);

  useEffect(() => {
    const generated = Array.from({ length: 60 }, () => ({
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 3 + 1,
      opacity: Math.random() * 0.3 + 0.05,
      pulse: Math.random() > 0.7,
      color: Math.random() > 0.85 ? "#EF4444" : Math.random() > 0.7 ? "#06B6D4" : "#3B82F6",
    }));
    setNodes(generated);
  }, []);

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      <svg className="absolute inset-0 w-full h-full" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="grid" width="60" height="60" patternUnits="userSpaceOnUse">
            <path d="M 60 0 L 0 0 0 60" fill="none" stroke="rgba(37,99,235,0.03)" strokeWidth="0.5"/>
          </pattern>
          <radialGradient id="fade" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(37,99,235,0.06)" />
            <stop offset="100%" stopColor="transparent" />
          </radialGradient>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)" />
        <rect width="100%" height="100%" fill="url(#fade)" />

        {nodes.slice(0, 20).map((node, i) => {
          const target = nodes[(i + 3) % nodes.length];
          return (
            <line
              key={`line-${i}`}
              x1={`${node.x}%`}
              y1={`${node.y}%`}
              x2={`${target.x}%`}
              y2={`${target.y}%`}
              stroke="rgba(37,99,235,0.05)"
              strokeWidth="0.5"
            />
          );
        })}

        {nodes.map((node, i) => (
          <g key={`node-${i}`}>
            {node.pulse && (
              <circle
                cx={`${node.x}%`}
                cy={`${node.y}%`}
                r={node.size * 4}
                fill="none"
                stroke="rgba(37,99,235,0.06)"
                strokeWidth="0.5"
              >
                <animate attributeName="r" values={`${node.size * 2};${node.size * 6};${node.size * 2}`} dur={`${3 + Math.random() * 4}s`} repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.12;0;0.12" dur={`${3 + Math.random() * 4}s`} repeatCount="indefinite" />
              </circle>
            )}
            <circle cx={`${node.x}%`} cy={`${node.y}%`} r={node.size} fill={node.color} opacity={node.opacity} />
          </g>
        ))}

        <line x1="0" y1="50%" x2="100%" y2="50%" stroke="rgba(239,68,68,0.06)" strokeWidth="1">
          <animate attributeName="y1" values="0%;100%;0%" dur="14s" repeatCount="indefinite"/>
          <animate attributeName="y2" values="0%;100%;0%" dur="14s" repeatCount="indefinite"/>
        </line>
      </svg>
    </div>
  );
}

/* ─── Dashboard Preview ─── */
function DashboardPreview() {
  return (
    <div className="relative mx-auto max-w-5xl">
      <div className="absolute -inset-4 bg-gradient-to-r from-primary/20 via-cyan-500/10 to-primary/20 rounded-3xl blur-2xl opacity-40" />
      <div className="relative rounded-2xl border border-border/40 bg-[#0D1117] shadow-2xl shadow-black/50 overflow-hidden">
        {/* Browser chrome */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border/20 bg-[#161B22]">
          <div className="flex gap-1.5">
            <div className="h-3 w-3 rounded-full bg-red-500/80" />
            <div className="h-3 w-3 rounded-full bg-yellow-500/80" />
            <div className="h-3 w-3 rounded-full bg-green-500/80" />
          </div>
          <div className="flex-1 mx-4">
            <div className="flex items-center gap-2 rounded-lg bg-[#0D1117] border border-border/20 px-3 py-1.5 max-w-md mx-auto">
              <Lock className="h-3 w-3 text-emerald-400" />
              <span className="text-xs text-muted-foreground font-mono">app.attacksec.io/dashboard</span>
            </div>
          </div>
        </div>

        {/* Dashboard content */}
        <div className="p-4 lg:p-6">
          <div className="grid grid-cols-4 gap-3 mb-4">
            {[
              { label: "Total Assets", value: "1,247", icon: Globe, color: "text-blue-400" },
              { label: "Open Ports", value: "89", icon: Server, color: "text-cyan-400" },
              { label: "Vulnerabilities", value: "23", icon: Bug, color: "text-red-400" },
              { label: "Risk Score", value: "72", icon: Shield, color: "text-amber-400" },
            ].map((stat) => (
              <div key={stat.label} className="rounded-xl border border-border/30 bg-card/50 p-3">
                <div className="flex items-center gap-2 mb-1">
                  <stat.icon className={`h-3.5 w-3.5 ${stat.color}`} />
                  <span className="text-[10px] text-muted-foreground">{stat.label}</span>
                </div>
                <span className="text-lg font-bold text-foreground">{stat.value}</span>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2 rounded-xl border border-border/30 bg-card/50 p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-medium text-foreground">Attack Surface</span>
                <span className="text-[10px] text-emerald-400">Live</span>
              </div>
              <div className="space-y-2">
                {["api.example.com", "cdn.example.com", "auth.example.com"].map((d, i) => (
                  <div key={d} className="flex items-center gap-2 text-xs">
                    <div className={`h-1.5 w-1.5 rounded-full ${i === 0 ? "bg-emerald-400" : i === 1 ? "bg-amber-400" : "bg-red-400"}`} />
                    <span className="font-mono text-muted-foreground">{d}</span>
                    <span className="ml-auto text-[10px] text-muted-foreground">{["4 open", "2 open", "7 open"][i]}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-border/30 bg-card/50 p-4">
              <span className="text-xs font-medium text-foreground block mb-3">Risk Distribution</span>
              <div className="space-y-2">
                {[
                  { label: "Critical", value: 2, color: "bg-red-500" },
                  { label: "High", value: 5, color: "bg-orange-500" },
                  { label: "Medium", value: 11, color: "bg-amber-500" },
                  { label: "Low", value: 5, color: "bg-emerald-500" },
                ].map((r) => (
                  <div key={r.label} className="flex items-center gap-2">
                    <div className={`h-1.5 w-1.5 rounded-full ${r.color}`} />
                    <span className="text-[10px] text-muted-foreground flex-1">{r.label}</span>
                    <span className="text-[10px] font-medium text-foreground">{r.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Floating cards */}
      <motion.div
        initial={{ opacity: 0, x: -20, y: 20 }}
        animate={{ opacity: 1, x: 0, y: 0 }}
        transition={{ delay: 0.8, duration: 0.6 }}
        className="absolute -left-8 top-1/4 hidden lg:block"
      >
        <div className="rounded-xl border border-border/40 bg-[#111827] shadow-xl p-3 backdrop-blur-sm">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            </div>
            <div>
              <p className="text-[10px] text-muted-foreground">SSL Valid</p>
              <p className="text-xs font-medium text-foreground">23 certs</p>
            </div>
          </div>
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, x: 20, y: -20 }}
        animate={{ opacity: 1, x: 0, y: 0 }}
        transition={{ delay: 1.0, duration: 0.6 }}
        className="absolute -right-8 top-1/3 hidden lg:block"
      >
        <div className="rounded-xl border border-border/40 bg-[#111827] shadow-xl p-3 backdrop-blur-sm">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-500/10">
              <AlertTriangle className="h-4 w-4 text-red-400" />
            </div>
            <div>
              <p className="text-[10px] text-muted-foreground">New Vuln</p>
              <p className="text-xs font-medium text-foreground">CVE-2024-1234</p>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

/* ─── Feature Card ─── */
function FeatureCard({ icon: Icon, title, description, color, delay = 0 }: {
  icon: any;
  title: string;
  description: string;
  color: string;
  delay?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-50px" }}
      transition={{ duration: 0.5, delay }}
      whileHover={{ y: -4, transition: { duration: 0.2 } }}
      className="group relative rounded-2xl border border-border/40 bg-card/50 backdrop-blur-sm p-6 hover:border-border/60 hover:bg-card/70 transition-all duration-300"
    >
      <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${color} mb-4 group-hover:scale-110 transition-transform duration-300`}>
        <Icon className="h-6 w-6" />
      </div>
      <h3 className="text-lg font-semibold text-foreground mb-2">{title}</h3>
      <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
    </motion.div>
  );
}

/* ─── Step Card ─── */
function StepCard({ step, title, description, icon: Icon, delay = 0 }: {
  step: string;
  title: string;
  description: string;
  icon: any;
  delay?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-50px" }}
      transition={{ duration: 0.5, delay }}
      className="relative text-center"
    >
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 mx-auto mb-5 relative">
        <Icon className="h-8 w-8 text-primary" />
        <div className="absolute -top-2 -right-2 flex h-6 w-6 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
          {step}
        </div>
      </div>
      <h3 className="text-lg font-semibold text-foreground mb-2">{title}</h3>
      <p className="text-sm text-muted-foreground leading-relaxed max-w-xs mx-auto">{description}</p>
    </motion.div>
  );
}

/* ─── Integration Card ─── */
function IntegrationCard({ name, icon: Icon, color }: { name: string; icon: any; color: string }) {
  return (
    <motion.div
      whileHover={{ scale: 1.05, y: -2 }}
      className="flex flex-col items-center gap-2 rounded-xl border border-border/30 bg-card/30 p-4 hover:border-border/50 hover:bg-card/50 transition-all cursor-default"
    >
      <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${color}`}>
        <Icon className="h-5 w-5" />
      </div>
      <span className="text-xs font-medium text-muted-foreground">{name}</span>
    </motion.div>
  );
}

/* ─── FAQ Item ─── */
function FAQItem({ question, answer }: { question: string; answer: string }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      className="border border-border/30 rounded-xl overflow-hidden"
    >
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between w-full px-6 py-4 text-left hover:bg-card/30 transition-colors"
      >
        <span className="text-sm font-medium text-foreground">{question}</span>
        <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`} />
      </button>
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="px-6 pb-4 text-sm text-muted-foreground leading-relaxed">
              {answer}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

/* ─── Section Wrapper ─── */
function Section({ children, className = "", id }: { children: React.ReactNode; className?: string; id?: string }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-100px" });

  return (
    <motion.section
      ref={ref}
      id={id}
      initial={{ opacity: 0 }}
      animate={isInView ? { opacity: 1 } : {}}
      transition={{ duration: 0.6 }}
      className={`relative z-10 ${className}`}
    >
      {children}
    </motion.section>
  );
}

/* ─── Main Landing Page ─── */
export default function LandingPage() {
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();
  const { scrollYProgress } = useScroll();
  const navBg = useTransform(scrollYProgress, [0, 0.05], ["rgba(9,9,11,0)", "rgba(9,9,11,0.95)"]);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    if (!loading && isAuthenticated) {
      router.push("/dashboard");
    }
  }, [isAuthenticated, loading, router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#09090B]">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[#09090B] border border-border/50">
          <img src="/icon.ico" alt="AttackSec" className="h-10 w-10 object-contain animate-pulse" />
        </div>
      </div>
    );
  }

  if (isAuthenticated) return null;

  const navLinks = [
    { label: "Platform", href: "#platform" },
    { label: "Features", href: "#features" },
    { label: "How It Works", href: "#how-it-works" },
    { label: "Enterprise", href: "#enterprise" },
    { label: "Integrations", href: "#integrations" },
    { label: "Pricing", href: "#pricing" },
  ];

  const features = [
    { icon: Globe, title: "Subdomain Discovery", description: "Automatically enumerate subdomains using certificate transparency logs, DNS brute-forcing, and OSINT sources.", color: "bg-blue-500/10 text-blue-400" },
    { icon: Server, title: "Port Scanning", description: "Identify open ports, running services, and version information across your entire perimeter.", color: "bg-cyan-500/10 text-cyan-400" },
    { icon: Lock, title: "SSL Certificate Monitoring", description: "Track certificate health, expiry dates, and configuration weaknesses before they become critical.", color: "bg-emerald-500/10 text-emerald-400" },
    { icon: Bug, title: "Vulnerability Detection", description: "Run nuclei templates against discovered assets to find known CVEs and security misconfigurations.", color: "bg-red-500/10 text-red-400" },
    { icon: Network, title: "Attack Graph", description: "Visualize your external attack surface as an interactive graph. See how assets connect and where risks concentrate.", color: "bg-purple-500/10 text-purple-400" },
    { icon: Radar, title: "Continuous Monitoring", description: "Track changes over time. Get alerted when new subdomains appear, ports open, or certificates expire.", color: "bg-amber-500/10 text-amber-400" },
    { icon: Search, title: "DNS Intelligence", description: "Deep DNS analysis with record history, zone transfers, and passive resolution tracking.", color: "bg-indigo-500/10 text-indigo-400" },
    { icon: FileText, title: "Professional Reports", description: "Generate comprehensive PDF reports with executive summaries, technical details, and remediation guidance.", color: "bg-pink-500/10 text-pink-400" },
    { icon: Target, title: "Risk Scoring", description: "Intelligent risk scoring engine that prioritizes vulnerabilities based on exploitability and business impact.", color: "bg-rose-500/10 text-rose-400" },
    { icon: Eye, title: "Technology Detection", description: "Identify frameworks, CMS platforms, server software, and CDN providers across all discovered assets.", color: "bg-teal-500/10 text-teal-400" },
    { icon: Activity, title: "Historical Changes", description: "Compare scans over time to track asset changes, new exposures, and remediation progress.", color: "bg-orange-500/10 text-orange-400" },
    { icon: Code, title: "REST API", description: "Full API access for integration with your existing security workflows, SIEM, and automation tools.", color: "bg-violet-500/10 text-violet-400" },
  ];

  const integrations = [
    { name: "GitHub", icon: Github, color: "bg-gray-500/10 text-gray-400" },
    { name: "GitLab", icon: Gitlab, color: "bg-orange-500/10 text-orange-400" },
    { name: "AWS", icon: Cloud, color: "bg-amber-500/10 text-amber-400" },
    { name: "Azure", icon: Cloud, color: "bg-blue-500/10 text-blue-400" },
    { name: "Google Cloud", icon: Cloud, color: "bg-emerald-500/10 text-emerald-400" },
    { name: "Slack", icon: MessageSquare, color: "bg-purple-500/10 text-purple-400" },
    { name: "Teams", icon: MessageSquare, color: "bg-indigo-500/10 text-indigo-400" },
    { name: "REST API", icon: Code, color: "bg-cyan-500/10 text-cyan-400" },
    { name: "Webhooks", icon: Webhook, color: "bg-pink-500/10 text-pink-400" },
  ];

  const testimonials = [
    {
      quote: "AttackSec helped us discover 40% more external assets than our previous solution. The automation is incredible.",
      name: "Sarah Chen",
      title: "CISO",
      company: "TechCorp Global",
    },
    {
      quote: "We went from manual recon taking days to automated scanning in under a minute. Game changer for our security team.",
      name: "Marcus Rodriguez",
      title: "Head of Security",
      company: "FinanceHub",
    },
    {
      quote: "The risk scoring and continuous monitoring give us real-time visibility into our expanding attack surface.",
      name: "Dr. Emily Watson",
      title: "VP of Engineering",
      company: "CyberShield Labs",
    },
  ];

  const faqs = [
    {
      question: "What is External Attack Surface Management (EASM)?",
      answer: "EASM is the process of discovering, inventorying, and monitoring all externally facing assets of an organization. It helps security teams understand their complete attack surface, identify vulnerabilities, and reduce risk from the outside-in perspective.",
    },
    {
      question: "How does AttackSec discover assets?",
      answer: "AttackSec uses multiple techniques including certificate transparency log analysis, DNS enumeration, passive reconnaissance, OSINT gathering, and active scanning to discover all externally facing assets including subdomains, IP addresses, open ports, and running services.",
    },
    {
      question: "Is there a free tier available?",
      answer: "Yes! AttackSec offers a free tier that includes scanning for a single domain with basic features. This includes subdomain discovery, port scanning, SSL analysis, and a limited number of vulnerability checks. No credit card required to get started.",
    },
    {
      question: "How often does the platform scan my assets?",
      answer: "By default, AttackSec performs continuous monitoring with scans running every 24 hours. Enterprise customers can configure custom scan schedules ranging from hourly to weekly, with real-time alerts for critical changes.",
    },
    {
      question: "Can I integrate AttackSec with my existing security tools?",
      answer: "Absolutely. AttackSec provides a full REST API, webhook integrations, and native connectors for popular security tools including SIEM platforms, ticketing systems, and collaboration tools like Slack and Microsoft Teams.",
    },
    {
      question: "What kind of vulnerabilities can AttackSec detect?",
      answer: "AttackSec uses nuclei templates and custom checks to detect known CVEs, misconfigurations, default credentials, exposed sensitive files, outdated software versions, SSL/TLS weaknesses, and hundreds of other security issues across your attack surface.",
    },
    {
      question: "Is my data secure with AttackSec?",
      answer: "Security is our top priority. All data is encrypted at rest and in transit, stored in SOC 2 compliant infrastructure, and we never store sensitive credentials. Our platform undergoes regular third-party security audits.",
    },
    {
      question: "Can I manage multiple organizations and projects?",
      answer: "Yes. AttackSec supports multi-tenant architecture with organizations and projects. You can separate different business units, clients, or environments, each with their own assets, scans, and team access controls.",
    },
  ];

  return (
    <div className="relative min-h-screen bg-[#09090B] overflow-hidden">
      <NetworkAnimation />

      {/* ═══ Navigation ═══ */}
      <motion.nav
        style={{ backgroundColor: navBg }}
        className="fixed top-0 left-0 right-0 z-50 backdrop-blur-md border-b border-border/10"
      >
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link href="/" className="flex items-center gap-2.5">
              <div className="relative flex h-8 w-8 items-center justify-center rounded-lg bg-[#09090B] border border-border/50 overflow-hidden">
                <img src="/icon.ico" alt="AttackSec" className="h-5 w-5 object-contain" />
                <div className="absolute inset-0 rounded-lg bg-gradient-to-br from-primary to-cyan-400 opacity-20 blur-sm" />
              </div>
              <span className="text-lg font-bold text-foreground tracking-tight">AttackSec</span>
            </Link>

            {/* Desktop nav */}
            <div className="hidden lg:flex items-center gap-1">
              {navLinks.map((link) => (
                <a
                  key={link.label}
                  href={link.href}
                  className="px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors rounded-lg hover:bg-muted/30"
                >
                  {link.label}
                </a>
              ))}
            </div>

            {/* CTA */}
            <div className="flex items-center gap-3">
              <Link href="/login" className="hidden sm:block px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
                Sign in
              </Link>
              <Link
                href="/register"
                className="px-4 py-2 text-sm font-semibold rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-all shadow-sm shadow-primary/20 hover:shadow-primary/30"
              >
                Get Started
              </Link>

              {/* Mobile menu button */}
              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="lg:hidden p-2 text-muted-foreground hover:text-foreground"
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  {mobileMenuOpen ? (
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  ) : (
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  )}
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* Mobile menu */}
        <AnimatePresence>
          {mobileMenuOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="lg:hidden border-t border-border/10 bg-[#09090B]/98 backdrop-blur-md"
            >
              <div className="px-6 py-4 space-y-1">
                {navLinks.map((link) => (
                  <a
                    key={link.label}
                    href={link.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className="block px-3 py-2.5 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors rounded-lg hover:bg-muted/30"
                  >
                    {link.label}
                  </a>
                ))}
                <div className="pt-3 border-t border-border/20 space-y-2">
                  <Link href="/login" className="block px-3 py-2.5 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
                    Sign in
                  </Link>
                  <Link href="/register" className="block px-3 py-2.5 text-sm font-semibold text-center rounded-lg bg-primary text-primary-foreground">
                    Get Started Free
                  </Link>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.nav>

      {/* ═══ Hero Section ═══ */}
      <Section className="pt-32 pb-20 lg:pt-40 lg:pb-28">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <div className="text-center max-w-4xl mx-auto mb-16">
            {/* Badge */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 mb-8"
            >
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
              </span>
              <span className="text-xs font-medium text-primary">External Attack Surface Management</span>
            </motion.div>

            {/* Headline */}
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1 }}
              className="text-4xl sm:text-5xl lg:text-7xl font-bold tracking-tight text-foreground leading-[1.08] mb-6"
            >
              Know what&rsquo;s exposed
              <br />
              <span className="bg-gradient-to-r from-primary via-cyan-400 to-primary bg-clip-text text-transparent">
                before attackers do
              </span>
            </motion.h1>

            {/* Subheadline */}
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="text-lg lg:text-xl text-muted-foreground max-w-2xl mx-auto mb-10 leading-relaxed"
            >
              Discover every subdomain, open port, certificate, and vulnerability across your
              entire external perimeter. Automated reconnaissance in 60 seconds.
            </motion.p>

            {/* CTA */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.3 }}
              className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16"
            >
              <Link
                href="/register"
                className="group flex items-center gap-2 px-8 py-3.5 rounded-xl bg-gradient-to-r from-primary to-cyan-500 text-primary-foreground font-semibold shadow-xl shadow-primary/25 hover:shadow-primary/40 transition-all text-base"
              >
                Start scanning free
                <ArrowRight className="h-4 w-4 group-hover:translate-x-0.5 transition-transform" />
              </Link>
              <a
                href="#how-it-works"
                className="flex items-center gap-2 px-8 py-3.5 rounded-xl border border-border/50 text-foreground font-medium hover:bg-muted/50 transition-all text-base"
              >
                <Play className="h-4 w-4" />
                See how it works
              </a>
            </motion.div>

            {/* Stats */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.8, delay: 0.5 }}
              className="flex items-center justify-center gap-8 sm:gap-14"
            >
              <div className="text-center">
                <p className="text-2xl sm:text-3xl font-bold text-foreground">&lt;60s</p>
                <p className="text-xs text-muted-foreground mt-1">Full recon</p>
              </div>
              <div className="h-8 w-px bg-border/30" />
              <div className="text-center">
                <p className="text-2xl sm:text-3xl font-bold text-foreground">100%</p>
                <p className="text-xs text-muted-foreground mt-1">Coverage</p>
              </div>
              <div className="h-8 w-px bg-border/30" />
              <div className="text-center">
                <p className="text-2xl sm:text-3xl font-bold text-foreground">24/7</p>
                <p className="text-xs text-muted-foreground mt-1">Monitoring</p>
              </div>
            </motion.div>
          </div>

          {/* Dashboard Preview */}
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.4 }}
          >
            <DashboardPreview />
          </motion.div>
        </div>
      </Section>

      {/* ═══ Trusted By ═══ */}
      <Section className="py-16 border-y border-border/10">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <motion.p
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="text-center text-sm text-muted-foreground mb-8"
          >
            Trusted by security teams worldwide
          </motion.p>
          <div className="flex flex-wrap items-center justify-center gap-x-12 gap-y-6">
            {["TechCorp", "FinanceHub", "CyberShield", "DataVault", "SecureNet", "CloudFirst"].map((company, i) => (
              <motion.div
                key={company}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="flex items-center gap-2 text-muted-foreground/40 hover:text-muted-foreground/60 transition-colors"
              >
                <Building2 className="h-5 w-5" />
                <span className="text-sm font-semibold tracking-wide">{company}</span>
              </motion.div>
            ))}
          </div>

          {/* Stats row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mt-12 max-w-3xl mx-auto">
            {[
              { value: 500, suffix: "+", label: "Organizations" },
              { value: 2, suffix: "M+", label: "Assets scanned" },
              { value: 99.9, suffix: "%", label: "Uptime" },
              { value: 150, suffix: "+", label: "Countries" },
            ].map((stat, i) => (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="text-center"
              >
                <p className="text-2xl font-bold text-foreground">
                  <AnimatedCounter target={stat.value} suffix={stat.suffix} />
                </p>
                <p className="text-xs text-muted-foreground mt-1">{stat.label}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </Section>

      {/* ═══ Why AttackSec ═══ */}
      <Section className="py-24" id="platform">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <div className="text-center mb-16">
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-xs font-semibold text-primary tracking-widest uppercase mb-3"
            >
              Why AttackSec
            </motion.p>
            <motion.h2
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-3xl sm:text-4xl font-bold text-foreground mb-4"
            >
              Enterprise-grade attack surface management
            </motion.h2>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-muted-foreground max-w-2xl mx-auto"
            >
              Built for security teams who need complete visibility, continuous monitoring,
              and actionable intelligence across their entire external perimeter.
            </motion.p>
          </div>

          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {[
              { icon: Shield, title: "Enterprise Architecture", description: "SOC 2 compliant infrastructure with role-based access, audit logs, and multi-tenant support.", color: "bg-blue-500/10 text-blue-400" },
              { icon: Radar, title: "Continuous Monitoring", description: "Automated 24/7 scanning with instant alerts for new exposures, certificate expiry, and configuration changes.", color: "bg-cyan-500/10 text-cyan-400" },
              { icon: Globe, title: "Complete Discovery", description: "Find every asset — subdomains, IPs, ports, services, technologies — across your entire external perimeter.", color: "bg-emerald-500/10 text-emerald-400" },
              { icon: BarChart3, title: "Risk Intelligence", description: "Intelligent risk scoring that prioritizes threats by exploitability, business impact, and attack path analysis.", color: "bg-amber-500/10 text-amber-400" },
            ].map((item, i) => (
              <motion.div
                key={item.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="rounded-2xl border border-border/40 bg-card/30 backdrop-blur-sm p-6 hover:border-border/60 hover:bg-card/50 transition-all duration-300"
              >
                <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${item.color} mb-4`}>
                  <item.icon className="h-6 w-6" />
                </div>
                <h3 className="text-base font-semibold text-foreground mb-2">{item.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{item.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </Section>

      {/* ═══ Features Grid ═══ */}
      <Section className="py-24 bg-card/20" id="features">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <div className="text-center mb-16">
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-xs font-semibold text-primary tracking-widest uppercase mb-3"
            >
              Features
            </motion.p>
            <motion.h2
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-3xl sm:text-4xl font-bold text-foreground mb-4"
            >
              Complete attack surface visibility
            </motion.h2>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-muted-foreground max-w-2xl mx-auto"
            >
              Every asset, every vulnerability, every risk — all in one platform.
            </motion.p>
          </div>

          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature, i) => (
              <FeatureCard key={feature.title} {...feature} delay={i * 0.05} />
            ))}
          </div>
        </div>
      </Section>

      {/* ═══ Platform Preview ═══ */}
      <Section className="py-24">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <div className="text-center mb-16">
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-xs font-semibold text-primary tracking-widest uppercase mb-3"
            >
              Platform
            </motion.p>
            <motion.h2
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-3xl sm:text-4xl font-bold text-foreground mb-4"
            >
              Beautiful, powerful, intuitive
            </motion.h2>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-muted-foreground max-w-2xl mx-auto"
            >
              A dashboard designed for security professionals. Real-time data, interactive visualizations, and actionable insights at your fingertips.
            </motion.p>
          </div>

          {/* Feature tabs */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8 max-w-3xl mx-auto">
            {[
              { label: "Dashboard", icon: BarChart3 },
              { label: "Assets", icon: Globe },
              { label: "Graph View", icon: Network },
              { label: "Reports", icon: FileText },
            ].map((tab, i) => (
              <motion.div
                key={tab.label}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className={`flex items-center justify-center gap-2 rounded-xl border px-4 py-3 cursor-default transition-all ${
                  i === 0
                    ? "border-primary/30 bg-primary/5 text-primary"
                    : "border-border/30 bg-card/20 text-muted-foreground hover:border-border/50"
                }`}
              >
                <tab.icon className="h-4 w-4" />
                <span className="text-sm font-medium">{tab.label}</span>
              </motion.div>
            ))}
          </div>

          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7 }}
          >
            <DashboardPreview />
          </motion.div>
        </div>
      </Section>

      {/* ═══ How It Works ═══ */}
      <Section className="py-24 bg-card/20" id="how-it-works">
        <div className="mx-auto max-w-6xl px-6 lg:px-8">
          <div className="text-center mb-16">
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-xs font-semibold text-primary tracking-widest uppercase mb-3"
            >
              How It Works
            </motion.p>
            <motion.h2
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-3xl sm:text-4xl font-bold text-foreground mb-4"
            >
              From zero to full visibility in minutes
            </motion.h2>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-muted-foreground max-w-xl mx-auto"
            >
              Four simple steps to discover and monitor your entire external attack surface.
            </motion.p>
          </div>

          <div className="grid gap-10 md:grid-cols-2 lg:grid-cols-4 relative">
            {/* Connector line */}
            <div className="hidden lg:block absolute top-8 left-[12.5%] right-[12.5%] h-px bg-gradient-to-r from-border/0 via-border/30 to-border/0" />

            <StepCard step="1" title="Create Workspace" description="Sign up and create your organization. Set up team members and access controls." icon={Building2} delay={0} />
            <StepCard step="2" title="Add Target" description="Enter your root domain. We support wildcards and multiple targets." icon={Target} delay={0.1} />
            <StepCard step="3" title="Discover Assets" description="Automated recon discovers subdomains, ports, certs, technologies, and vulnerabilities." icon={Scan} delay={0.2} />
            <StepCard step="4" title="Monitor & Report" description="Continuous monitoring with alerts. Generate professional reports anytime." icon={Bell} delay={0.3} />
          </div>
        </div>
      </Section>

      {/* ═══ Enterprise Capabilities ═══ */}
      <Section className="py-24" id="enterprise">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <div className="grid lg:grid-cols-2 gap-16 items-center">
            <div>
              <motion.p
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                className="text-xs font-semibold text-primary tracking-widest uppercase mb-3"
              >
                Enterprise
              </motion.p>
              <motion.h2
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                className="text-3xl sm:text-4xl font-bold text-foreground mb-6"
              >
                Built for teams that take security seriously
              </motion.h2>
              <motion.p
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                className="text-muted-foreground mb-8 leading-relaxed"
              >
                Multi-tenant architecture with role-based access, audit logging, and enterprise-grade security features designed for organizations of any size.
              </motion.p>

              <div className="grid grid-cols-2 gap-4">
                {[
                  { icon: Building2, label: "Organizations" },
                  { icon: Briefcase, label: "Projects" },
                  { icon: Users, label: "Role-Based Access" },
                  { icon: FileText, label: "Audit Logs" },
                  { icon: Key, label: "API Keys" },
                  { icon: Bell, label: "Notifications" },
                  { icon: Zap, label: "Automation" },
                  { icon: Code, label: "Integrations" },
                ].map((item, i) => (
                  <motion.div
                    key={item.label}
                    initial={{ opacity: 0, x: -10 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.05 }}
                    className="flex items-center gap-3 p-3 rounded-xl border border-border/20 bg-card/20"
                  >
                    <item.icon className="h-4 w-4 text-primary" />
                    <span className="text-sm text-muted-foreground">{item.label}</span>
                  </motion.div>
                ))}
              </div>
            </div>

            {/* Visual */}
            <motion.div
              initial={{ opacity: 0, x: 30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              className="relative"
            >
              <div className="absolute -inset-4 bg-gradient-to-r from-primary/10 to-cyan-500/10 rounded-3xl blur-2xl opacity-50" />
              <div className="relative rounded-2xl border border-border/40 bg-card/50 backdrop-blur-sm p-8">
                <div className="space-y-4">
                  {[
                    { role: "Admin", access: "Full access", color: "bg-red-500" },
                    { role: "Manager", access: "Projects & scans", color: "bg-amber-500" },
                    { role: "Analyst", access: "Read & scan", color: "bg-blue-500" },
                    { role: "Viewer", access: "Read only", color: "bg-emerald-500" },
                  ].map((perm, i) => (
                    <motion.div
                      key={perm.role}
                      initial={{ opacity: 0, x: 20 }}
                      whileInView={{ opacity: 1, x: 0 }}
                      viewport={{ once: true }}
                      transition={{ delay: 0.3 + i * 0.1 }}
                      className="flex items-center justify-between p-4 rounded-xl border border-border/30 bg-card/50"
                    >
                      <div className="flex items-center gap-3">
                        <div className={`h-2 w-2 rounded-full ${perm.color}`} />
                        <span className="text-sm font-medium text-foreground">{perm.role}</span>
                      </div>
                      <span className="text-xs text-muted-foreground">{perm.access}</span>
                    </motion.div>
                  ))}
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </Section>

      {/* ═══ Integrations ═══ */}
      <Section className="py-24 bg-card/20" id="integrations">
        <div className="mx-auto max-w-5xl px-6 lg:px-8">
          <div className="text-center mb-16">
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-xs font-semibold text-primary tracking-widest uppercase mb-3"
            >
              Integrations
            </motion.p>
            <motion.h2
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-3xl sm:text-4xl font-bold text-foreground mb-4"
            >
              Connects with your stack
            </motion.h2>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-muted-foreground max-w-xl mx-auto"
            >
              Native integrations and a powerful API to fit into your existing security workflows.
            </motion.p>
          </div>

          <div className="grid grid-cols-3 sm:grid-cols-5 gap-3">
            {integrations.map((integration) => (
              <IntegrationCard key={integration.name} {...integration} />
            ))}
          </div>
        </div>
      </Section>

      {/* ═══ Testimonials ═══ */}
      <Section className="py-24">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <div className="text-center mb-16">
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-xs font-semibold text-primary tracking-widest uppercase mb-3"
            >
              Testimonials
            </motion.p>
            <motion.h2
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-3xl sm:text-4xl font-bold text-foreground mb-4"
            >
              Loved by security teams
            </motion.h2>
          </div>

          <div className="grid gap-6 md:grid-cols-3">
            {testimonials.map((testimonial, i) => (
              <motion.div
                key={testimonial.name}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="rounded-2xl border border-border/40 bg-card/30 backdrop-blur-sm p-6 hover:border-border/60 transition-all"
              >
                <div className="flex gap-1 mb-4">
                  {[...Array(5)].map((_, j) => (
                    <Star key={j} className="h-4 w-4 fill-amber-400 text-amber-400" />
                  ))}
                </div>
                <p className="text-sm text-foreground leading-relaxed mb-6">&ldquo;{testimonial.quote}&rdquo;</p>
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary font-semibold text-sm">
                    {testimonial.name.split(" ").map((n) => n[0]).join("")}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">{testimonial.name}</p>
                    <p className="text-xs text-muted-foreground">{testimonial.title}, {testimonial.company}</p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </Section>

      {/* ═══ Pricing ═══ */}
      <Section className="py-24 bg-card/20" id="pricing">
        <div className="mx-auto max-w-5xl px-6 lg:px-8">
          <div className="text-center mb-16">
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-xs font-semibold text-primary tracking-widest uppercase mb-3"
            >
              Pricing
            </motion.p>
            <motion.h2
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-3xl sm:text-4xl font-bold text-foreground mb-4"
            >
              Start free, scale when ready
            </motion.h2>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-muted-foreground max-w-xl mx-auto"
            >
              No credit card required. Full features on every plan.
            </motion.p>
          </div>

          <div className="grid gap-6 md:grid-cols-3 max-w-4xl mx-auto">
            {[
              { name: "Free", price: "$0", period: "forever", description: "Perfect for getting started", features: ["1 domain", "Daily scans", "Basic reporting", "Community support"], cta: "Get Started", highlight: false },
              { name: "Pro", price: "$49", period: "/month", description: "For growing security teams", features: ["Unlimited domains", "Hourly scans", "Advanced reporting", "API access", "Email alerts", "Priority support"], cta: "Start Free Trial", highlight: true },
              { name: "Enterprise", price: "Custom", period: "", description: "For large organizations", features: ["Everything in Pro", "Custom scan schedules", "SSO & SAML", "Dedicated support", "SLA guarantee", "On-premise option"], cta: "Contact Sales", highlight: false },
            ].map((plan, i) => (
              <motion.div
                key={plan.name}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className={`rounded-2xl border p-6 ${
                  plan.highlight
                    ? "border-primary/40 bg-card/50 shadow-xl shadow-primary/10 relative"
                    : "border-border/40 bg-card/30"
                }`}
              >
                {plan.highlight && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <span className="px-3 py-1 rounded-full bg-primary text-[10px] font-semibold text-primary-foreground">
                      Most Popular
                    </span>
                  </div>
                )}
                <h3 className="text-lg font-semibold text-foreground mb-1">{plan.name}</h3>
                <p className="text-sm text-muted-foreground mb-4">{plan.description}</p>
                <div className="mb-6">
                  <span className="text-4xl font-bold text-foreground">{plan.price}</span>
                  <span className="text-sm text-muted-foreground">{plan.period}</span>
                </div>
                <ul className="space-y-2.5 mb-6">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Check className="h-4 w-4 text-emerald-400 shrink-0" />
                      {feature}
                    </li>
                  ))}
                </ul>
                <Link
                  href="/register"
                  className={`block w-full text-center py-2.5 rounded-xl text-sm font-semibold transition-all ${
                    plan.highlight
                      ? "bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm shadow-primary/20"
                      : "border border-border/50 text-foreground hover:bg-muted/50"
                  }`}
                >
                  {plan.cta}
                </Link>
              </motion.div>
            ))}
          </div>
        </div>
      </Section>

      {/* ═══ FAQ ═══ */}
      <Section className="py-24">
        <div className="mx-auto max-w-3xl px-6 lg:px-8">
          <div className="text-center mb-16">
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-xs font-semibold text-primary tracking-widest uppercase mb-3"
            >
              FAQ
            </motion.p>
            <motion.h2
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-3xl sm:text-4xl font-bold text-foreground mb-4"
            >
              Frequently asked questions
            </motion.h2>
          </div>

          <div className="space-y-3">
            {faqs.map((faq) => (
              <FAQItem key={faq.question} {...faq} />
            ))}
          </div>
        </div>
      </Section>

      {/* ═══ Final CTA ═══ */}
      <Section className="py-24">
        <div className="mx-auto max-w-4xl px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="relative rounded-3xl border border-border/40 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-sm p-10 lg:p-16 text-center overflow-hidden"
          >
            {/* Background glow */}
            <div className="absolute inset-0 bg-gradient-to-r from-primary/5 via-transparent to-cyan-500/5" />

            <div className="relative z-10">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[#09090B] border border-border/50 mx-auto mb-6 shadow-xl overflow-hidden">
                <img src="/icon.ico" alt="AttackSec" className="h-10 w-10 object-contain" />
              </div>
              <h2 className="text-3xl sm:text-4xl font-bold text-foreground mb-4">
                Start mapping your attack surface today
              </h2>
              <p className="text-muted-foreground max-w-lg mx-auto mb-8">
                Free for a single domain. No credit card required. Full recon in under 60 seconds.
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <Link
                  href="/register"
                  className="group flex items-center gap-2 px-8 py-3.5 rounded-xl bg-gradient-to-r from-primary to-cyan-500 text-primary-foreground font-semibold shadow-xl shadow-primary/25 hover:shadow-primary/40 transition-all text-base"
                >
                  Create free account
                  <ArrowRight className="h-4 w-4 group-hover:translate-x-0.5 transition-transform" />
                </Link>
                <Link
                  href="/login"
                  className="flex items-center gap-2 px-8 py-3.5 rounded-xl border border-border/50 text-foreground font-medium hover:bg-muted/50 transition-all text-base"
                >
                  Sign in to dashboard
                </Link>
              </div>
            </div>
          </motion.div>
        </div>
      </Section>

      {/* ═══ Footer ═══ */}
      <footer className="relative z-10 border-t border-border/10 bg-card/10">
        <div className="mx-auto max-w-7xl px-6 lg:px-8 py-16">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-8 mb-12">
            {/* Brand */}
            <div className="col-span-2 md:col-span-1">
              <div className="flex items-center gap-2 mb-4">
                <div className="relative flex h-7 w-7 items-center justify-center rounded-lg bg-[#09090B] border border-border/50 overflow-hidden">
                  <img src="/icon.ico" alt="AttackSec" className="h-4 w-4 object-contain" />
                </div>
                <span className="text-sm font-bold text-foreground">AttackSec</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed mb-4">
                External Attack Surface Management Platform
              </p>
              <div className="flex gap-3">
                {["Twitter", "GitHub", "LinkedIn"].map((social) => (
                  <span key={social} className="text-xs text-muted-foreground/40 hover:text-muted-foreground cursor-pointer transition-colors">
                    {social}
                  </span>
                ))}
              </div>
            </div>

            {/* Links */}
            {[
              { title: "Product", links: ["Features", "Pricing", "Integrations", "API", "Changelog"] },
              { title: "Resources", links: ["Documentation", "Blog", "Guides", "Status", "Support"] },
              { title: "Company", links: ["About", "Careers", "Contact", "Partners", "Legal"] },
              { title: "Legal", links: ["Privacy Policy", "Terms of Service", "Cookie Policy", "Security"] },
            ].map((section) => (
              <div key={section.title}>
                <h4 className="text-xs font-semibold text-foreground mb-3">{section.title}</h4>
                <ul className="space-y-2">
                  {section.links.map((link) => (
                    <li key={link}>
                      <span className="text-xs text-muted-foreground hover:text-foreground cursor-pointer transition-colors">
                        {link}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <div className="border-t border-border/10 pt-6 flex flex-col sm:flex-row items-center justify-between gap-4">
            <p className="text-xs text-muted-foreground">
              &copy; 2024 AttackSec. All rights reserved.
            </p>
            <p className="text-xs text-muted-foreground/40">
              Built for security professionals
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}