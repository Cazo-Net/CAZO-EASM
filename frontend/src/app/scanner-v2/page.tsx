"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Globe,
  Radar,
  Loader2,
  CheckCircle,
  XCircle,
  AlertTriangle,
  ChevronRight,
  Clock,
  Shield,
  Server,
  Lock,
  Cpu,
  GitBranch,
  Activity,
  Play,
  Pause,
  RotateCw,
} from "lucide-react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PageHeader } from "@/components/common/PageHeader";
import { DocTooltip } from "@/components/common/DocTooltip";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  getScannerV2Health,
  runScanV2,
  type ScanV2Health,
  type ScanV2Result,
} from "@/lib/api";

const PIPELINE_STAGES = [
  { id: "asset_discovery", label: "Asset Discovery", icon: Globe },
  { id: "dns_intelligence", label: "DNS Intelligence", icon: Server },
  { id: "network_intelligence", label: "Network Intelligence", icon: Activity },
  { id: "technology_fingerprint", label: "Technology Fingerprint", icon: Cpu },
  { id: "certificate_analysis", label: "Certificate Analysis", icon: Lock },
  { id: "risk_evaluation", label: "Risk Evaluation", icon: Shield },
  { id: "graph_mapping", label: "Graph Mapping", icon: GitBranch },
];

function getRiskColor(score: number): string {
  if (score >= 80) return "text-severity-critical bg-severity-critical/10 border-severity-critical/20";
  if (score >= 60) return "text-severity-high bg-severity-high/10 border-severity-high/20";
  if (score >= 40) return "text-severity-medium bg-severity-medium/10 border-severity-medium/20";
  if (score >= 20) return "text-severity-low bg-severity-low/10 border-severity-low/20";
  return "text-success bg-success/10 border-success/20";
}

function getRiskLabel(score: number): string {
  if (score >= 80) return "Critical";
  if (score >= 60) return "High";
  if (score >= 40) return "Medium";
  if (score >= 20) return "Low";
  return "Minimal";
}

export default function ScannerV2Page() {
  const [domain, setDomain] = useState("");
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState<ScanV2Health | null>(null);
  const [scanResult, setScanResult] = useState<ScanV2Result | null>(null);
  const [pipelineProgress, setPipelineProgress] = useState<Record<string, number>>({});
  const [pipelineStatus, setPipelineStatus] = useState<Record<string, "pending" | "running" | "complete" | "error">>({});
  const [currentStage, setCurrentStage] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [scanType, setScanType] = useState<"full" | "quick">("full");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    getScannerV2Health().then(setHealth).catch(() => {});
  }, []);

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const handleScan = async () => {
    if (!domain.trim()) return;
    setLoading(true);
    setError("");
    setScanResult(null);
    setPipelineProgress({});
    setPipelineStatus({});

    try {
      const result = await runScanV2({
        domain: domain.trim(),
        scan_type: scanType,
      });
      setScanResult(result);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Scan failed");
    } finally {
      setLoading(false);
    }
  };

  const handleWebSocketScan = useCallback(() => {
    if (!domain.trim()) return;
    setLoading(true);
    setError("");
    setScanResult(null);
    setPipelineProgress({});
    setPipelineStatus({});
    setCurrentStage(null);

    const maxRetries = 3;
    let retryCount = 0;

    const connect = () => {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${window.location.host}/api/v1/scanner-v2/scan/stream`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        retryCount = 0;
        ws.send(JSON.stringify({ domain: domain.trim(), scan_type: scanType }));
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "progress") {
            setPipelineProgress((prev) => ({ ...prev, [msg.stage]: msg.progress }));
            setPipelineStatus((prev) => ({ ...prev, [msg.stage]: "running" }));
            setCurrentStage(msg.stage);
          } else if (msg.type === "complete") {
            setScanResult(msg.result);
            setLoading(false);
            if (currentStage) {
              setPipelineStatus((prev) => ({ ...prev, [currentStage]: "complete" }));
            }
          } else if (msg.type === "error") {
            setError(msg.message);
            setLoading(false);
          }
        } catch {
          setError("Invalid message from server");
        }
      };

      ws.onerror = () => {
        if (retryCount < maxRetries) {
          retryCount++;
          const delay = Math.min(1000 * 2 ** retryCount, 10000);
          setError(`Connection lost, retrying in ${delay / 1000}s...`);
          setTimeout(connect, delay);
        } else {
          setError("WebSocket connection failed after retries");
          setLoading(false);
        }
      };

      ws.onclose = (event) => {
        if (!event.wasClean && retryCount < maxRetries) {
          const delay = Math.min(1000 * 2 ** retryCount, 10000);
          setError(`Connection closed, reconnecting in ${delay / 1000}s...`);
          retryCount++;
          setTimeout(connect, delay);
        } else if (retryCount >= maxRetries) {
          setLoading(false);
        }
      };
    };

    connect();
  }, [domain, scanType, currentStage]);

  const riskScore = scanResult?.risk_score?.risk_score ?? 0;

  return (
    <ProtectedRoute>
      <div className="page-container">
        <div className="py-6">
          <PageHeader
            title="Scanner v2"
            description="Deep recon pipeline — watch each stage resolve in real time"
            icon={<Radar className="h-5 w-5" />}
            breadcrumbs={[
              { label: "Home", href: "/dashboard" },
              { label: "Scanner v2" },
            ]}
          />

          <div className="mt-8 grid gap-6">
            {/* Scan Input */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Globe className="h-4 w-4" />
                  Target Domain
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex gap-3">
                  <Input
                    placeholder="example.com"
                    value={domain}
                    onChange={(e) => setDomain(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleScan()}
                    className="flex-1"
                  />
                  <div className="flex gap-2">
                    <Button
                      variant={scanType === "full" ? "default" : "outline"}
                      size="sm"
                      onClick={() => setScanType("full")}
                    >
                      Full
                    </Button>
                    <Button
                      variant={scanType === "quick" ? "default" : "outline"}
                      size="sm"
                      onClick={() => setScanType("quick")}
                    >
                      Quick
                    </Button>
                  </div>
                  <Button
                    onClick={handleWebSocketScan}
                    disabled={loading || !domain.trim()}
                  >
                    {loading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Play className="h-4 w-4" />
                    )}
                    Stream
                  </Button>
                  <Button
                    onClick={handleScan}
                    disabled={loading || !domain.trim()}
                    variant="outline"
                  >
                    {loading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Radar className="h-4 w-4" />
                    )}
                    Run
                  </Button>
                </div>
                {error && (
                  <p className="mt-2 text-sm text-signal-red">{error}</p>
                )}
              </CardContent>
            </Card>

            {/* Pipeline Visualization */}
            {(loading || scanResult) && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <Activity className="h-4 w-4" />
                    Pipeline Progress
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {PIPELINE_STAGES.map((stage) => {
                      const Icon = stage.icon;
                      const progress = pipelineProgress[stage.id] ?? 0;
                      const status = pipelineStatus[stage.id] ?? "pending";
                      const isRunning = currentStage === stage.id;

                      return (
                        <div key={stage.id} className="flex items-center gap-3">
                          <div className="flex items-center gap-2 w-48">
                            {status === "complete" ? (
                              <CheckCircle className="h-4 w-4 text-success" />
                            ) : status === "error" ? (
                              <XCircle className="h-4 w-4 text-signal-red" />
                            ) : isRunning ? (
                              <Loader2 className="h-4 w-4 text-cyan-signal animate-spin" />
                            ) : (
                              <Icon className="h-4 w-4 text-muted-foreground" />
                            )}
                            <span className="text-sm">{stage.label}</span>
                          </div>
                          <div className="flex-1">
                            <Progress
                              value={progress * 100}
                              className="h-2"
                            />
                          </div>
                          <span className="text-xs text-muted-foreground w-12 text-right">
                            {Math.round(progress * 100)}%
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Risk Score */}
            {scanResult && (
              <div className="grid gap-6 md:grid-cols-3">
                <Card>
                  <CardContent className="pt-6">
                    <div className="text-center">
                      <div className={`inline-flex items-center justify-center w-20 h-20 rounded-full border-2 ${getRiskColor(riskScore)}`}>
                        <span className="text-2xl font-bold">{riskScore}</span>
                      </div>
                      <p className="mt-2 text-sm font-medium">
                        {getRiskLabel(riskScore)}
                      </p>
                      <p className="text-xs text-muted-foreground flex items-center justify-center gap-1.5">
                        Risk Score <DocTooltip article="threat-score" />
                      </p>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="pt-6">
                    <div className="space-y-3">
                      <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">Subdomains</span>
                        <span className="text-sm font-medium">
                          {scanResult.subdomains?.length ?? 0}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">Engine</span>
                        <Badge variant="outline">{scanResult.scan_engine}</Badge>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">Status</span>
                        <Badge variant={scanResult.success ? "default" : "destructive"}>
                          {scanResult.success ? "Success" : "Failed"}
                        </Badge>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="pt-6">
                    <div className="space-y-2">
                      <p className="text-sm font-medium">Scanner Status</p>
                      {Object.entries(scanResult.scanner_status || {}).map(([key, val]) => (
                        <div key={key} className="flex justify-between text-xs">
                          <span className="text-muted-foreground">{key}</span>
                          <span>{String(val)}</span>
                        </div>
                      ))}
                      {Object.keys(scanResult.scanner_status || {}).length === 0 && (
                        <p className="text-xs text-muted-foreground">No scanner status available</p>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}

            {/* Subdomains List */}
            {scanResult && scanResult.subdomains && scanResult.subdomains.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <Globe className="h-4 w-4" />
                    Discovered Subdomains ({scanResult.subdomains.length})
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="max-h-64 overflow-y-auto space-y-1">
                    {scanResult.subdomains.map((sub) => (
                      <div
                        key={sub}
                        className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-muted/50 text-sm"
                      >
                        <ChevronRight className="h-3 w-3 text-muted-foreground" />
                        <span>{sub}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Health Info */}
            {health && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <Shield className="h-4 w-4" />
                    Scanner Health
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div>
                      <p className="text-sm font-medium mb-2">Registered Scanners</p>
                      <div className="space-y-1">
                        {health.registered_scanners.map((s) => (
                          <div key={s.name} className="flex items-center gap-2 text-xs">
                            <CheckCircle className="h-3 w-3 text-success" />
                            <span>{s.name}</span>
                            <Badge variant="outline" className="ml-auto">
                              {s.category}
                            </Badge>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-sm font-medium mb-2">Pipeline Stages</p>
                      <div className="space-y-1">
                        {health.pipeline_stages.map((stage) => (
                          <div key={stage} className="flex items-center gap-2 text-xs">
                            <CheckCircle className="h-3 w-3 text-success" />
                            <span>{stage}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
