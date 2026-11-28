"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Boxes,
  Loader2,
  Shield,
  AlertTriangle,
  Globe,
  Search,
  Filter,
  Download,
  RefreshCw,
} from "lucide-react";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { PageHeader } from "@/components/common/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { RiskSummary } from "@/components/supply-chain/RiskSummary";
import { VendorGrid } from "@/components/supply-chain/VendorGrid";
import { DataFlowDiagram } from "@/components/supply-chain/DataFlowDiagram";

const API_BASE = "";

interface Technology {
  name: string;
  category: string;
  vendor_type: string;
  confidence: number;
  version?: string;
  evidence?: string[];
}

interface ScanOption {
  id: string;
  target: string;
  created_at: string;
  status: string;
}

function SupplyChainContent() {
  const [scans, setScans] = useState<ScanOption[]>([]);
  const [selectedScanId, setSelectedScanId] = useState<string>("");
  const [technologies, setTechnologies] = useState<Technology[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanLoading, setScanLoading] = useState(false);
  const [filterVendorType, setFilterVendorType] = useState<string>("all");
  const [filterRisk, setFilterRisk] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Fetch recent scans
  const fetchScans = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/scans/?limit=20`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token") || sessionStorage.getItem("access_token") || ""}`,
        },
      });
      if (res.ok) {
        const data = await res.json();
        const scanList = (data.scans || data.items || []).filter(
          (s: any) => s.status === "completed"
        );
        setScans(scanList);
        if (scanList.length > 0 && !selectedScanId) {
          setSelectedScanId(scanList[0].id);
        }
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [selectedScanId]);

  // Fetch scan technologies
  const fetchTechnologies = useCallback(async () => {
    if (!selectedScanId) return;
    setScanLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/scans/${selectedScanId}`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token") || sessionStorage.getItem("access_token") || ""}`,
        },
      });
      if (res.ok) {
        const data = await res.json();
        const techs =
          data.results?.technologies ||
          data.technologies ||
          data.data?.technologies ||
          [];
        setTechnologies(techs);
      }
    } catch {
      // ignore
    } finally {
      setScanLoading(false);
    }
  }, [selectedScanId]);

  useEffect(() => {
    fetchScans();
  }, [fetchScans]);

  useEffect(() => {
    if (selectedScanId) fetchTechnologies();
  }, [selectedScanId, fetchTechnologies]);

  // Compute stats
  const totalServices = technologies.length;
  const thirdParty = technologies.filter(
    (t) => t.vendor_type === "third_party_service"
  ).length;
  const saasPlatforms = technologies.filter(
    (t) => t.vendor_type === "saas_platform"
  ).length;
  const firstParty = technologies.filter(
    (t) => t.vendor_type === "first_party_infra"
  ).length;
  const securityTools = technologies.filter(
    (t) => t.vendor_type === "security_tool"
  ).length;

  // Vendor type counts for concentration risk
  const vendorTypeCounts: Record<string, number> = {};
  technologies.forEach((t) => {
    const vt = t.vendor_type || "unknown";
    vendorTypeCounts[vt] = (vendorTypeCounts[vt] || 0) + 1;
  });

  // Category counts
  const categoryCounts: Record<string, number> = {};
  technologies.forEach((t) => {
    const cat = t.category || "Other";
    categoryCounts[cat] = (categoryCounts[cat] || 0) + 1;
  });

  // Filter technologies
  const filteredTechs = technologies.filter((t) => {
    if (filterVendorType !== "all" && t.vendor_type !== filterVendorType)
      return false;
    if (filterRisk !== "all") {
      const risk = t.confidence >= 80 ? "high" : t.confidence >= 50 ? "medium" : "low";
      if (risk !== filterRisk) return false;
    }
    if (
      searchQuery &&
      !t.name.toLowerCase().includes(searchQuery.toLowerCase()) &&
      !t.category.toLowerCase().includes(searchQuery.toLowerCase())
    )
      return false;
    return true;
  });

  const vendorTypes = [
    { value: "all", label: "All Types" },
    { value: "third_party_service", label: "Third-Party Services" },
    { value: "saas_platform", label: "SaaS Platforms" },
    { value: "first_party_infra", label: "First-Party Infrastructure" },
    { value: "security_tool", label: "Security Tools" },
    { value: "cloud_provider", label: "Cloud Providers" },
    { value: "devops_tool", label: "DevOps Tools" },
  ];

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-6xl mx-auto px-6 py-8">
        <PageHeader
          title="Supply Chain Intelligence"
          description="Third-party vendor analysis, concentration risk, and dependency mapping"
          icon={<Boxes className="h-5 w-5" />}
        />

        {/* Scan selector */}
        <SectionCard title="Select Scan" icon={<Search className="h-4 w-4" />} className="mt-6">
          <div className="flex gap-3">
            <select
              value={selectedScanId}
              onChange={(e) => setSelectedScanId(e.target.value)}
              className="flex-1 border border-border rounded-md bg-background px-3 py-2 text-sm"
              disabled={loading}
            >
              {loading ? (
                <option>Loading scans...</option>
              ) : scans.length === 0 ? (
                <option>No completed scans found</option>
              ) : (
                scans.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.target} — {new Date(s.created_at).toLocaleDateString()}
                  </option>
                ))
              )}
            </select>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchScans}
              disabled={loading}
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </SectionCard>

        {/* Loading */}
        {scanLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* Summary stats */}
        {!scanLoading && technologies.length > 0 && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mt-6">
              <div className="border border-border/50 rounded-lg p-4 bg-muted/5">
                <div className="text-xs text-muted-foreground">Total Services</div>
                <div className="text-2xl font-bold mt-1">{totalServices}</div>
              </div>
              <div className="border border-border/50 rounded-lg p-4 bg-muted/5">
                <div className="text-xs text-muted-foreground">Third-Party</div>
                <div className="text-2xl font-bold mt-1 text-blue-400">{thirdParty}</div>
              </div>
              <div className="border border-border/50 rounded-lg p-4 bg-muted/5">
                <div className="text-xs text-muted-foreground">SaaS Platforms</div>
                <div className="text-2xl font-bold mt-1 text-purple-400">{saasPlatforms}</div>
              </div>
              <div className="border border-border/50 rounded-lg p-4 bg-muted/5">
                <div className="text-xs text-muted-foreground">First-Party</div>
                <div className="text-2xl font-bold mt-1 text-green-400">{firstParty}</div>
              </div>
              <div className="border border-border/50 rounded-lg p-4 bg-muted/5">
                <div className="text-xs text-muted-foreground">Security Tools</div>
                <div className="text-2xl font-bold mt-1 text-orange-400">{securityTools}</div>
              </div>
            </div>

            {/* Risk summary */}
            <RiskSummary vendorTypeCounts={vendorTypeCounts} />

            {/* Vendor grid */}
            <SectionCard
              title="Discovered Services"
              icon={<Globe className="h-4 w-4" />}
              className="mt-6"
            >
              {/* Filters */}
              <div className="flex flex-wrap gap-3 mb-4">
                <div className="flex items-center gap-2">
                  <Filter className="h-3.5 w-3.5 text-muted-foreground" />
                  <select
                    value={filterVendorType}
                    onChange={(e) => setFilterVendorType(e.target.value)}
                    className="border border-border rounded bg-background px-2 py-1 text-xs"
                  >
                    {vendorTypes.map((vt) => (
                      <option key={vt.value} value={vt.value}>
                        {vt.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex items-center gap-2">
                  <Shield className="h-3.5 w-3.5 text-muted-foreground" />
                  <select
                    value={filterRisk}
                    onChange={(e) => setFilterRisk(e.target.value)}
                    className="border border-border rounded bg-background px-2 py-1 text-xs"
                  >
                    <option value="all">All Risk Levels</option>
                    <option value="high">High Risk</option>
                    <option value="medium">Medium Risk</option>
                    <option value="low">Low Risk</option>
                  </select>
                </div>
                <Input
                  placeholder="Search services..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-48 h-7 text-xs"
                />
                <div className="ml-auto text-xs text-muted-foreground">
                  {filteredTechs.length} of {totalServices} services
                </div>
              </div>

              <VendorGrid technologies={filteredTechs} />
            </SectionCard>

            {/* Data flow */}
            <DataFlowDiagram technologies={technologies} categoryCounts={categoryCounts} />
          </>
        )}

        {/* Empty state */}
        {!scanLoading && technologies.length === 0 && !loading && (
          <EmptyState
            icon={<Boxes className="h-8 w-8" />}
            title="No supply chain data"
            description={
              selectedScanId
                ? "This scan didn't include technology detection. Run a full scan to get supply chain data."
                : "Select a completed scan to view supply chain intelligence."
            }
          />
        )}
      </div>
    </div>
  );
}

export default function SupplyChainPage() {
  return (
    <ProtectedRoute>
      <SupplyChainContent />
    </ProtectedRoute>
  );
}
