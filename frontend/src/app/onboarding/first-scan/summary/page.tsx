"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  Globe,
  Network,
  Server,
  Bug,
  Shield,
  ArrowRight,
  ExternalLink,
  AlertTriangle,
} from "lucide-react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { getScan, listSubdomains, listPorts, listTechnologies, listVulnerabilities } from "@/lib/api";
import type { ScanDetail, Subdomain, Port, Technology, Vulnerability } from "@/types";
import { CazoLogo } from "@/components/marketing/CazoLogo";

function SummaryContent() {
  const router = useRouter();
  const { user } = useAuth();
  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [subdomains, setSubdomains] = useState<Subdomain[]>([]);
  const [ports, setPorts] = useState<Port[]>([]);
  const [technologies, setTechnologies] = useState<Technology[]>([]);
  const [vulnerabilities, setVulnerabilities] = useState<Vulnerability[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const scanId = (user?.preferences as any)?.onboarding?.first_scan_id;

  useEffect(() => {
    if (!scanId) {
      setLoading(false);
      setError("No first scan found. Run a scan from the dashboard to see results here.");
      return;
    }

    async function load() {
      try {
        const detail = await getScan(scanId);
        setScan(detail);

        const [subs, p, techs, vulns] = await Promise.all([
          listSubdomains(scanId).catch(() => []),
          listPorts(scanId).catch(() => []),
          listTechnologies(scanId).catch(() => []),
          listVulnerabilities(scanId).catch(() => []),
        ]);
        setSubdomains(subs);
        setPorts(p);
        setTechnologies(techs);
        setVulnerabilities(vulns);
      } catch (e: any) {
        setError("Couldn't load scan results.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [scanId]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-24">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-phosphor border-t-transparent" />
        <p className="text-sm text-muted-foreground">Loading your results…</p>
      </div>
    );
  }

  if (error || !scan) {
    return (
      <div className="flex flex-col items-center gap-4 py-24 text-center">
        <AlertTriangle className="h-10 w-10 text-muted-foreground/40" />
        <p className="text-sm text-muted-foreground max-w-md">
          {error || "No scan results to display."}
        </p>
        <Button onClick={() => router.push("/dashboard")}>
          Go to Dashboard
        </Button>
      </div>
    );
  }

  const topFindings = vulnerabilities
    .filter((v) => v.severity === "critical" || v.severity === "high")
    .slice(0, 2);

  const findingsBySeverity = {
    critical: vulnerabilities.filter((v) => v.severity === "critical").length,
    high: vulnerabilities.filter((v) => v.severity === "high").length,
    medium: vulnerabilities.filter((v) => v.severity === "medium").length,
    low: vulnerabilities.filter((v) => v.severity === "low").length,
  };

  return (
    <div className="max-w-2xl mx-auto">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center mb-8"
      >
        <p className="font-mono text-sm text-muted-foreground mb-1">
          Results for
        </p>
        <p className="font-mono text-xl text-foreground">{scan.domain}</p>
      </motion.div>

      {/* Stats grid */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="grid grid-cols-2 gap-3 mb-8"
      >
        <div className="rounded-xl border border-border/50 bg-card/40 p-4">
          <div className="flex items-center gap-2 mb-2">
            <Globe className="h-4 w-4 text-phosphor" />
            <span className="text-xs text-muted-foreground">Subdomains</span>
          </div>
          <p className="text-2xl font-bold text-foreground">{subdomains.length}</p>
        </div>
        <div className="rounded-xl border border-border/50 bg-card/40 p-4">
          <div className="flex items-center gap-2 mb-2">
            <Server className="h-4 w-4 text-cyan-signal" />
            <span className="text-xs text-muted-foreground">Open Ports</span>
          </div>
          <p className="text-2xl font-bold text-foreground">{ports.length}</p>
        </div>
        <div className="rounded-xl border border-border/50 bg-card/40 p-4">
          <div className="flex items-center gap-2 mb-2">
            <Network className="h-4 w-4 text-neon-violet" />
            <span className="text-xs text-muted-foreground">Technologies</span>
          </div>
          <p className="text-2xl font-bold text-foreground">{technologies.length}</p>
        </div>
        <div className="rounded-xl border border-border/50 bg-card/40 p-4">
          <div className="flex items-center gap-2 mb-2">
            <Bug className="h-4 w-4 text-signal-red" />
            <span className="text-xs text-muted-foreground">Findings</span>
          </div>
          <p className="text-2xl font-bold text-foreground">{vulnerabilities.length}</p>
        </div>
      </motion.div>

      {/* Severity breakdown */}
      {vulnerabilities.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="rounded-xl border border-border/50 bg-card/40 p-4 mb-6"
        >
          <p className="text-sm font-medium text-foreground mb-3">Findings by severity</p>
          <div className="flex gap-4 text-xs">
            {findingsBySeverity.critical > 0 && (
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-destructive" />
                <span className="text-muted-foreground">{findingsBySeverity.critical} critical</span>
              </span>
            )}
            {findingsBySeverity.high > 0 && (
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-signal-red" />
                <span className="text-muted-foreground">{findingsBySeverity.high} high</span>
              </span>
            )}
            {findingsBySeverity.medium > 0 && (
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-warning" />
                <span className="text-muted-foreground">{findingsBySeverity.medium} medium</span>
              </span>
            )}
            {findingsBySeverity.low > 0 && (
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-cyan-signal" />
                <span className="text-muted-foreground">{findingsBySeverity.low} low</span>
              </span>
            )}
          </div>
        </motion.div>
      )}

      {/* Top findings */}
      {topFindings.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="rounded-xl border border-border/50 bg-card/40 p-4 mb-8"
        >
          <p className="text-sm font-medium text-foreground mb-3">What stood out</p>
          <div className="space-y-2">
            {topFindings.map((v) => (
              <div
                key={v.id}
                className="flex items-start gap-3 rounded-lg border border-border/40 bg-obsidian/40 px-3 py-2"
              >
                <span
                  className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${
                    v.severity === "critical"
                      ? "bg-destructive"
                      : "bg-signal-red"
                  }`}
                />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-mono text-foreground truncate">
                    {v.name || "Finding"}
                  </p>
                  <p className="text-xs text-muted-foreground truncate">
                    {v.host || ""}
                  </p>
                </div>
                <span
                  className={`shrink-0 rounded border px-1.5 py-0.5 font-mono text-[9px] uppercase ${
                    v.severity === "critical"
                      ? "text-destructive border-destructive/20 bg-destructive/10"
                      : "text-signal-red border-signal-red/20 bg-signal-red/10"
                  }`}
                >
                  {v.severity}
                </span>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {vulnerabilities.length === 0 && subdomains.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="rounded-xl border border-phosphor/20 bg-phosphor/5 p-4 mb-8 text-center"
        >
          <Shield className="h-8 w-8 text-phosphor mx-auto mb-2" />
          <p className="text-sm text-foreground font-medium">No findings detected</p>
          <p className="text-xs text-muted-foreground mt-1">
            No critical or high-severity issues found on your surface. Keep monitoring — things change.
          </p>
        </motion.div>
      )}

      {/* Next steps */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="space-y-3"
      >
        <p className="text-sm font-medium text-foreground">Next steps</p>
        <div className="grid gap-2">
          <button
            onClick={() => router.push("/vulnerabilities")}
            className="flex items-center gap-3 rounded-xl border border-border/50 bg-card/40 p-4 text-left transition-colors hover:border-phosphor/30"
          >
            <Bug className="h-5 w-5 text-signal-red shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-foreground">Review your findings</p>
              <p className="text-xs text-muted-foreground">All vulnerabilities, sorted by severity</p>
            </div>
            <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0" />
          </button>
          <button
            onClick={() => router.push("/graph")}
            className="flex items-center gap-3 rounded-xl border border-border/50 bg-card/40 p-4 text-left transition-colors hover:border-phosphor/30"
          >
            <Network className="h-5 w-5 text-neon-violet shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-foreground">See how it all connects</p>
              <p className="text-xs text-muted-foreground">Your attack graph — assets linked by shared infrastructure</p>
            </div>
            <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0" />
          </button>
          <button
            onClick={() => router.push("/settings")}
            className="flex items-center gap-3 rounded-xl border border-border/50 bg-card/40 p-4 text-left transition-colors hover:border-phosphor/30"
          >
            <Shield className="h-5 w-5 text-phosphor shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-foreground">Set up notifications</p>
              <p className="text-xs text-muted-foreground">Get alerted when new findings appear</p>
            </div>
            <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0" />
          </button>
        </div>

        <div className="pt-2 text-center">
          <button
            onClick={() => router.push("/dashboard")}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            Go to dashboard
          </button>
        </div>
      </motion.div>
    </div>
  );
}

export default function FirstScanSummaryPage() {
  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-[#09090B]">
        <header className="border-b border-border/40 bg-void/80 backdrop-blur-xl">
          <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-6">
            <CazoLogo />
          </div>
        </header>
        <div className="mx-auto max-w-5xl px-6 py-12">
          <SummaryContent />
        </div>
      </div>
    </ProtectedRoute>
  );
}
