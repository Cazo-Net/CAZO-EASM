"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  GitCompare,
  Loader2,
  Search,
  ArrowRight,
  Plus,
  Minus,
  Equal,
  Globe,
  Server,
  Lock,
  Bug,
  Cpu,
} from "lucide-react";
import { listScans, compareScans } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PageHeader } from "@/components/common/PageHeader";

interface ScanItem {
  id: string;
  domain: string;
  created_at: string;
  status: string;
}

interface CompareResult {
  scan_a: { id: string; domain: string; date: string };
  scan_b: { id: string; domain: string; date: string };
  summary: {
    scan_a: Record<string, number>;
    scan_b: Record<string, number>;
  };
  diff: {
    subdomains: { added: string[][]; removed: string[][]; unchanged_count: number };
    ports: { added: string[][]; removed: string[][]; unchanged_count: number };
    technologies: { added: string[][]; removed: string[][]; unchanged_count: number };
    vulnerabilities: { added: string[][]; removed: string[][]; unchanged_count: number };
  };
}

function ComparePageContent() {
  const [scans, setScans] = useState<ScanItem[]>([]);
  const [selectedA, setSelectedA] = useState<string>("");
  const [selectedB, setSelectedB] = useState<string>("");
  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingScans, setLoadingScans] = useState(true);
  const [searchA, setSearchA] = useState("");
  const [searchB, setSearchB] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchScans = async () => {
      try {
        const data = await listScans({ status: "completed" });
        setScans(data);
      } catch {
        setError("Failed to load scans");
      } finally {
        setLoadingScans(false);
      }
    };
    fetchScans();
  }, []);

  const handleCompare = useCallback(async () => {
    if (!selectedA || !selectedB || selectedA === selectedB) return;
    setLoading(true);
    setError(null);
    try {
      const data = await compareScans(selectedA, selectedB);
      setResult(data);
    } catch {
      setError("Failed to compare scans. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [selectedA, selectedB]);

  const filteredA = scans.filter((s) =>
    !searchA || s.domain.toLowerCase().includes(searchA.toLowerCase())
  );
  const filteredB = scans.filter((s) =>
    !searchB || s.domain.toLowerCase().includes(searchB.toLowerCase())
  );

  const scanA = scans.find((s) => s.id === selectedA);
  const scanB = scans.find((s) => s.id === selectedB);

  const diffSections = result
    ? [
        { label: "Subdomains", icon: Globe, added: result.diff.subdomains.added, removed: result.diff.subdomains.removed },
        { label: "Ports", icon: Server, added: result.diff.ports.added, removed: result.diff.ports.removed },
        { label: "Technologies", icon: Cpu, added: result.diff.technologies.added, removed: result.diff.technologies.removed },
        { label: "Vulnerabilities", icon: Bug, added: result.diff.vulnerabilities.added, removed: result.diff.vulnerabilities.removed },
      ]
    : [];

  return (
    <div className="page-container-lg">
      <div className="py-6 space-y-6">
        <PageHeader
          title="Compare Scans"
          description="Pick two scans. See what changed between them."
          icon={<GitCompare className="h-5 w-5" />}
          breadcrumbs={[{ label: "Home", href: "/dashboard" }, { label: "Compare Scans" }]}
        />

        {/* Selectors */}
        <div className="grid gap-4 md:grid-cols-2">
          {/* Scan A */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="glass-strong rounded-xl p-6 gradient-border">
            <h3 className="font-semibold mb-3 text-sm">Scan A (Before)</h3>
            <div className="relative mb-3">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                placeholder="Search scans..."
                value={searchA}
                onChange={(e) => setSearchA(e.target.value)}
                className="w-full h-9 pl-9 pr-3 rounded-lg bg-muted/50 border border-border text-sm focus:border-brand/40 focus:outline-none"
              />
            </div>
            <div className="max-h-48 overflow-y-auto space-y-1 scrollbar-thin">
              {loadingScans ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              ) : filteredA.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">No completed scans</p>
              ) : (
                filteredA.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => setSelectedA(s.id)}
                    className={`w-full text-left p-3 rounded-lg border transition-all text-sm ${
                      selectedA === s.id
                        ? "border-primary/50 bg-brand/10"
                        : "border-border hover:bg-muted/50"
                    }`}
                  >
                    <p className="font-medium font-mono">{s.domain}</p>
                    <p className="text-xs text-muted-foreground">{new Date(s.created_at).toLocaleDateString()}</p>
                  </button>
                ))
              )}
            </div>
          </motion.div>

          {/* Scan B */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }} className="glass-strong rounded-xl p-6 gradient-border">
            <h3 className="font-semibold mb-3 text-sm">Scan B (After)</h3>
            <div className="relative mb-3">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                placeholder="Search scans..."
                value={searchB}
                onChange={(e) => setSearchB(e.target.value)}
                className="w-full h-9 pl-9 pr-3 rounded-lg bg-muted/50 border border-border text-sm focus:border-brand/40 focus:outline-none"
              />
            </div>
            <div className="max-h-48 overflow-y-auto space-y-1 scrollbar-thin">
              {loadingScans ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              ) : filteredB.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">No completed scans</p>
              ) : (
                filteredB.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => setSelectedB(s.id)}
                    className={`w-full text-left p-3 rounded-lg border transition-all text-sm ${
                      selectedB === s.id
                        ? "border-primary/50 bg-brand/10"
                        : "border-border hover:bg-muted/50"
                    }`}
                  >
                    <p className="font-medium font-mono">{s.domain}</p>
                    <p className="text-xs text-muted-foreground">{new Date(s.created_at).toLocaleDateString()}</p>
                  </button>
                ))
              )}
            </div>
          </motion.div>
        </div>

        {/* Compare Button */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-center">
          <Button
            onClick={handleCompare}
            disabled={!selectedA || !selectedB || selectedA === selectedB || loading}
            className="bg-primary hover:from-primary/90 hover:to-cyan-signal/90 text-brand-foreground shadow shadow-primary/20 px-8"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <GitCompare className="h-4 w-4 mr-2" />
            )}
            Compare Scans
          </Button>
        </motion.div>

        {error && (
          <div className="text-center text-sm text-destructive bg-destructive/10 rounded-lg px-4 py-2">
            {error}
          </div>
        )}

        {/* Results */}
        {result && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <span className="font-medium font-mono text-foreground">{result.scan_a.domain}</span>
              <ArrowRight className="h-4 w-4" />
              <span className="font-medium font-mono text-foreground">{result.scan_b.domain}</span>
            </div>

            {diffSections.map((section) => {
              const SectionIcon = section.icon;
              const totalChanges = section.added.length + section.removed.length;
              return (
                <div key={section.label} className="glass rounded-xl overflow-hidden">
                  <div className="flex items-center justify-between p-4 border-b border-border">
                    <div className="flex items-center gap-2">
                      <SectionIcon className="h-4 w-4 text-brand" />
                      <h3 className="font-semibold text-sm">{section.label}</h3>
                    </div>
                    <Badge variant={totalChanges > 0 ? "default" : "secondary"} className="text-xs">
                      {totalChanges === 0 ? (
                        <span className="flex items-center gap-1"><Equal className="h-3 w-3" /> No change</span>
                      ) : (
                        <span>{totalChanges} change{totalChanges !== 1 ? "s" : ""}</span>
                      )}
                    </Badge>
                  </div>
                  <div className="divide-y divide-border/20">
                    {section.added.map((item: any, i: number) => (
                      <div key={`add-${i}`} className="flex items-center gap-3 px-4 py-2 text-sm">
                        <Plus className="h-3.5 w-3.5 text-success shrink-0" />
                        <span className="text-success font-medium">+ </span>
                        <span className="truncate">{Array.isArray(item) ? item.join(" → ") : String(item)}</span>
                      </div>
                    ))}
                    {section.removed.map((item: any, i: number) => (
                      <div key={`rem-${i}`} className="flex items-center gap-3 px-4 py-2 text-sm">
                        <Minus className="h-3.5 w-3.5 text-destructive shrink-0" />
                        <span className="text-destructive font-medium">- </span>
                        <span className="truncate">{Array.isArray(item) ? item.join(" → ") : String(item)}</span>
                      </div>
                    ))}
                    {totalChanges === 0 && (
                      <div className="px-4 py-3 text-xs text-muted-foreground text-center">No differences</div>
                    )}
                  </div>
                </div>
              );
            })}
          </motion.div>
        )}
      </div>
    </div>
  );
}

export default function ComparePage() {
  return (
    <ProtectedRoute>
      <ComparePageContent />
    </ProtectedRoute>
  );
}
