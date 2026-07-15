"use client";

import { useEffect, useState } from "react";
import {
  Sparkles,
  TrendingUp,
  AlertTriangle,
  Shield,
  Globe,
  Lock,
  Cpu,
  Activity,
  ArrowRight,
  Loader2,
  RefreshCw,
  Zap,
  Clock,
  BarChart3,
  Lightbulb,
  Settings,
  BookOpen,
} from "lucide-react";
import { motion } from "framer-motion";
import Link from "next/link";
import { getAIDashboard, getAIRecommendations } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";
import { cn } from "@/lib/utils";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import type { AIDashboard, AIRecommendation } from "@/types";

function AIDashboardContent() {
  const [dashboard, setDashboard] = useState<AIDashboard | null>(null);
  const [recommendations, setRecommendations] = useState<AIRecommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [dash, recs] = await Promise.all([getAIDashboard(), getAIRecommendations()]);
      setDashboard(dash);
      setRecommendations(recs);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const [dash, recs] = await Promise.all([getAIDashboard(), getAIRecommendations()]);
      setDashboard(dash);
      setRecommendations(recs);
    } catch {
      // silently fail
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const summary = dashboard?.today_summary || {};
  const health = dashboard?.platform_health || {};
  const certAlerts = dashboard?.certificate_alerts || {};

  return (
    <div className="min-h-screen">
      <div className="border-b border-border/50 bg-card/30 backdrop-blur-xl sticky top-0 z-10">
        <div className="mx-auto max-w-7xl px-6 py-5">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
                <Sparkles className="h-6 w-6 text-primary" />
                AI Intelligence
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                AI-powered insights for your attack surface.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="flex items-center gap-2 rounded-lg bg-primary/10 px-3 py-2 text-xs font-medium text-primary hover:bg-primary/20 transition-colors"
              >
                {generating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                Refresh
              </button>
              <Link
                href="/ai/copilot"
                className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-primary to-cyan-500 px-4 py-2 text-xs font-medium text-white hover:opacity-90 transition-opacity"
              >
                <Sparkles className="h-3.5 w-3.5" />
                Ask AI
              </Link>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-6 py-8 space-y-8">
        {/* Key Metrics */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { label: "Total Assets", value: health.total_assets || 0, icon: Globe, color: "text-primary", bg: "bg-primary/10" },
            { label: "Risk Score", value: summary.risk_score !== null ? `${summary.risk_score}/100` : "N/A", icon: Shield, color: "text-emerald-400", bg: "bg-emerald-500/10" },
            { label: "Certificate Alerts", value: (certAlerts.expiring_soon || 0) + (certAlerts.expired || 0), icon: Lock, color: "text-amber-400", bg: "bg-amber-500/10" },
            { label: "Technologies", value: dashboard?.technology_changes?.unique || 0, icon: Cpu, color: "text-violet-400", bg: "bg-violet-500/10" },
          ].map((metric) => (
            <motion.div
              key={metric.label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-xl border border-border/50 bg-card/60 p-5"
            >
              <div className="flex items-center justify-between mb-3">
                <div className={cn("flex h-9 w-9 items-center justify-center rounded-lg", metric.bg)}>
                  <metric.icon className={cn("h-4 w-4", metric.color)} />
                </div>
              </div>
              <p className="text-2xl font-bold">{metric.value}</p>
              <p className="text-xs text-muted-foreground mt-1">{metric.label}</p>
            </motion.div>
          ))}
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Recommendations */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="lg:col-span-2 rounded-xl border border-border/50 bg-card/60 overflow-hidden"
          >
            <div className="flex items-center justify-between border-b border-border/30 px-6 py-4">
              <div className="flex items-center gap-2">
                <Lightbulb className="h-4 w-4 text-amber-400" />
                <h2 className="text-sm font-semibold">Top Recommendations</h2>
              </div>
              <Link href="/ai/recommendations" className="text-xs text-primary hover:text-primary/80">
                View all
              </Link>
            </div>
            <div className="divide-y divide-border/20">
              {recommendations.length === 0 ? (
                <div className="p-6 text-center text-sm text-muted-foreground">
                  No recommendations yet. Click Refresh to generate.
                </div>
              ) : (
                recommendations.slice(0, 5).map((rec) => (
                  <div key={rec.id} className="flex items-start gap-3 px-6 py-4 hover:bg-muted/20 transition-colors">
                    <div className={cn(
                      "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg",
                      rec.priority === "critical" ? "bg-red-500/10 text-red-400" :
                      rec.priority === "high" ? "bg-amber-500/10 text-amber-400" :
                      "bg-blue-500/10 text-blue-400"
                    )}>
                      <Lightbulb className="h-3.5 w-3.5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium">{rec.title}</p>
                      <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{rec.description}</p>
                      <div className="flex items-center gap-2 mt-1.5">
                        <span className={cn(
                          "rounded-full px-2 py-0.5 text-[10px] font-medium",
                          rec.priority === "critical" ? "bg-red-500/10 text-red-400" :
                          rec.priority === "high" ? "bg-amber-500/10 text-amber-400" :
                          "bg-blue-500/10 text-blue-400"
                        )}>
                          {rec.priority}
                        </span>
                        <span className="text-[10px] text-muted-foreground">{rec.category}</span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </motion.div>

          {/* Quick Actions */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="rounded-xl border border-border/50 bg-card/60 overflow-hidden"
          >
            <div className="border-b border-border/30 px-6 py-4">
              <h2 className="text-sm font-semibold flex items-center gap-2">
                <Zap className="h-4 w-4 text-primary" />
                Quick Actions
              </h2>
            </div>
            <div className="p-4 space-y-2">
              {[
                { label: "Ask AI Copilot", href: "/ai/copilot", icon: Sparkles, color: "text-primary" },
                { label: "View Knowledge", href: "/ai/knowledge", icon: BookOpen, color: "text-cyan-400" },
                { label: "Check Recommendations", href: "/ai/recommendations", icon: Lightbulb, color: "text-amber-400" },
                { label: "AI Settings", href: "/ai/settings", icon: Settings, color: "text-violet-400" },
              ].map((action) => (
                <Link
                  key={action.href}
                  href={action.href}
                  className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm hover:bg-muted/30 transition-colors"
                >
                  <action.icon className={cn("h-4 w-4", action.color)} />
                  <span className="flex-1">{action.label}</span>
                  <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
                </Link>
              ))}
            </div>
          </motion.div>
        </div>

        {/* Suggested Questions */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="rounded-xl border border-border/50 bg-card/60 overflow-hidden"
        >
          <div className="border-b border-border/30 px-6 py-4">
            <h2 className="text-sm font-semibold flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-cyan-400" />
              Suggested Questions
            </h2>
          </div>
          <div className="p-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {[
              "Summarize my platform status",
              "What changed today?",
              "Show certificates expiring this month",
              "Which assets require attention?",
              "Explain the exposure score",
              "Show projects with the most activity",
              "Find production assets",
              "Generate an executive summary",
              "Show recently added assets",
            ].map((q) => (
              <Link
                key={q}
                href={`/ai/copilot?q=${encodeURIComponent(q)}`}
                className="flex items-center gap-2 rounded-lg border border-border/30 px-3 py-2 text-sm text-muted-foreground hover:bg-muted/30 hover:text-foreground transition-colors"
              >
                <Sparkles className="h-3 w-3 text-primary/50 shrink-0" />
                {q}
              </Link>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  );
}

export default function AIDashboardPage() {
  return (
    <ProtectedRoute>
      <AIDashboardContent />
    </ProtectedRoute>
  );
}
