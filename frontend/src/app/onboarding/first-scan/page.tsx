"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  Globe,
  Server,
  Activity,
  Cpu,
  Lock,
  Shield,
  GitBranch,
  Loader2,
  CheckCircle,
  XCircle,
  ArrowRight,
  Clock,
  Radar,
} from "lucide-react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { createScan, getErrorMessage, getScan } from "@/lib/api";
import type { ScanDetail } from "@/types";
import { CazoLogo } from "@/components/marketing/CazoLogo";

const PIPELINE_STAGES = [
  { id: "asset_discovery", label: "Subdomain Discovery", icon: Globe, explanation: "We check public certificate logs and DNS records — this never touches your infrastructure directly." },
  { id: "dns_intelligence", label: "DNS Intelligence", icon: Server, explanation: "Resolving hostnames, checking for mail servers, name servers, and DNS configuration." },
  { id: "network_intelligence", label: "Port Scanning", icon: Activity, explanation: "Probing common ports to find open services and running software." },
  { id: "technology_fingerprint", label: "Technology Detection", icon: Cpu, explanation: "Identifying web servers, frameworks, and software versions from HTTP headers and responses." },
  { id: "certificate_analysis", label: "Certificate Analysis", icon: Lock, explanation: "Examining TLS certificates for related domains, expiration dates, and issuer details." },
  { id: "risk_evaluation", label: "Risk Evaluation", icon: Shield, explanation: "Correlating findings against known vulnerabilities and misconfigurations." },
  { id: "graph_mapping", label: "Graph Mapping", icon: GitBranch, explanation: "Connecting assets through shared infrastructure to map your attack surface." },
];

function getStageProgress(scan: ScanDetail | null, stageIndex: number): "complete" | "active" | "pending" {
  if (!scan) return "pending";
  if (scan.status === "completed") return "complete";
  if (scan.status === "failed") return stageIndex === 0 ? "active" : "pending";
  const stageProgress = scan.progress || 0;
  const stageThreshold = ((stageIndex + 1) / PIPELINE_STAGES.length) * 100;
  const prevThreshold = (stageIndex / PIPELINE_STAGES.length) * 100;
  if (stageProgress >= stageThreshold) return "complete";
  if (stageProgress >= prevThreshold) return "active";
  return "pending";
}

function FirstScanContent() {
  const router = useRouter();
  const { user, updateOnboardingState } = useAuth();
  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const pollRef = useRef<NodeJS.Timeout | null>(null);
  const elapsedRef = useRef<NodeJS.Timeout | null>(null);

  const domain = (user?.preferences as any)?.onboarding?.first_scan_domain;

  const startScan = useCallback(async () => {
    if (!domain) return;
    setCreating(true);
    setError("");
    try {
      const result = await createScan(domain, "quick", {
        scan_size: "small",
        max_subdomains: 20,
        port_mode: "fast",
        include_nuclei: false,
        subdomain_tools: ["default"],
      });
      setScan(result as any);
      await updateOnboardingState({ first_scan_id: result.id });
    } catch (e: any) {
      setError(
        getErrorMessage(e, "Couldn't start the scan. You can try again or skip to the dashboard.")
      );
    } finally {
      setCreating(false);
    }
  }, [domain, updateOnboardingState]);

  useEffect(() => {
    if (domain && !scan && !creating) {
      startScan();
    }
  }, [domain]);

  useEffect(() => {
    if (!scan || scan.status === "completed" || scan.status === "failed") return;

    pollRef.current = setInterval(async () => {
      try {
        const updated = await getScan(scan.id);
        setScan(updated);
        if (updated.status === "completed" || updated.status === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
          if (updated.status === "completed") {
            await updateOnboardingState({ completed: true });
          }
        }
      } catch {
        // poll error — keep trying
      }
    }, 3000);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [scan?.id, scan?.status]);

  useEffect(() => {
    if (!scan || scan.status === "completed" || scan.status === "failed") return;
    elapsedRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => {
      if (elapsedRef.current) clearInterval(elapsedRef.current);
    };
  }, [scan?.status]);

  if (!domain) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
        <Radar className="h-10 w-10 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          No domain found from onboarding. You can skip to the dashboard and start a scan manually.
        </p>
        <Button onClick={() => router.push("/dashboard")} variant="outline">
          Go to Dashboard
        </Button>
      </div>
    );
  }

  if (creating && !scan) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24">
        <Loader2 className="h-10 w-10 animate-spin text-phosphor" />
        <p className="text-sm text-muted-foreground">
          Starting your first scan of <span className="font-mono text-foreground">{domain}</span>…
        </p>
      </div>
    );
  }

  if (error && !scan) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
        <XCircle className="h-10 w-10 text-destructive" />
        <p className="text-sm text-muted-foreground max-w-md">{error}</p>
        <div className="flex gap-2">
          <Button onClick={startScan} variant="outline">
            Retry
          </Button>
          <Button onClick={() => router.push("/dashboard")}>
            Skip to Dashboard
          </Button>
        </div>
      </div>
    );
  }

  const isRunning = scan && scan.status !== "completed" && scan.status !== "failed";
  const isFailed = scan?.status === "failed";
  const isComplete = scan?.status === "completed";

  return (
    <div className="max-w-2xl mx-auto">
      {/* Domain header */}
      <div className="text-center mb-8">
        <p className="font-mono text-sm text-muted-foreground">
          Scanning
        </p>
        <p className="font-mono text-xl text-foreground mt-1">{domain}</p>
        {isRunning && (
          <p className="text-xs text-muted-foreground mt-2 flex items-center justify-center gap-1.5">
            <Clock className="h-3 w-3" />
            {elapsed}s elapsed
          </p>
        )}
      </div>

      {/* Pipeline stages */}
      <div className="space-y-3">
        {PIPELINE_STAGES.map((stage, i) => {
          const stageStatus = getStageProgress(scan, i);
          const Icon = stage.icon;
          return (
            <motion.div
              key={stage.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className={`rounded-xl border p-4 transition-colors ${
                stageStatus === "complete"
                  ? "border-border bg-muted/40"
                  : stageStatus === "active"
                  ? "border-cyan-signal/30 bg-cyan-signal/5"
                  : "border-border bg-card"
              }`}
            >
              <div className="flex items-center gap-3">
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-lg ${
                    stageStatus === "complete"
                      ? "bg-phosphor/10 text-phosphor"
                      : stageStatus === "active"
                      ? "bg-cyan-signal/10 text-cyan-signal"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  {stageStatus === "complete" ? (
                    <CheckCircle className="h-4 w-4" />
                  ) : stageStatus === "active" ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Icon className="h-4 w-4" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground">
                    {stage.label}
                  </p>
                  {stageStatus === "active" && (
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {stage.explanation}
                    </p>
                  )}
                  {stageStatus === "complete" && (
                    <p className="text-xs text-phosphor/70 mt-0.5">
                      Done
                    </p>
                  )}
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Status footer */}
      {isRunning && (
        <div className="mt-8 text-center">
          <p className="text-xs text-muted-foreground">
            Results stream in as they resolve — you don&apos;t need to wait for completion.
          </p>
        </div>
      )}

      {isFailed && (
        <div className="mt-8 flex flex-col items-center gap-3">
          <p className="text-sm text-destructive">
            Scan hit an issue: {scan?.error_message || "Unknown error"}
          </p>
          <div className="flex gap-2">
            <Button onClick={startScan} variant="outline">
              Retry
            </Button>
            <Button onClick={() => router.push("/dashboard")}>
              Skip to Dashboard
            </Button>
          </div>
        </div>
      )}

      {isComplete && (
        <div className="mt-8 flex flex-col items-center gap-3">
          <p className="text-sm text-muted-foreground">
            Scan complete — here&apos;s what we found.
          </p>
          <Button onClick={() => router.push(`/onboarding/first-scan/summary`)}>
            View Results
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Skip link always available */}
      <div className="mt-6 text-center">
        <button
          onClick={() => router.push("/dashboard")}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          Skip to dashboard
        </button>
      </div>
    </div>
  );
}

export default function FirstScanPage() {
  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-background">
        <header className="border-b border-border bg-void/80">
          <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-6">
            <CazoLogo />
          </div>
        </header>
        <div className="mx-auto max-w-5xl px-6 py-12">
          <FirstScanContent />
        </div>
      </div>
    </ProtectedRoute>
  );
}
