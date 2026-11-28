"use client";

import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import { listScans, getAssetGraph } from "@/lib/api";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  Waypoints,
  Globe,
  Server,
  Bug,
  Loader2,
  ShieldAlert,
  Search,
  X,
  Radio,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useChecklistAutoComplete } from "@/components/onboarding/GettingStartedChecklist";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  useNodesState,
  useEdgesState,
  MarkerType,
  Position,
  Handle,
  type Node,
  type Edge,
  type NodeProps,
  ReactFlowProvider,
  useReactFlow,
  Panel,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { computeForceLayout, type RawGraphNode, type RawGraphEdge } from "@/lib/graphLayout";
import type { Scan } from "@/types";

// ---------------------------------------------------------------------------
// Type metadata + severity
// ---------------------------------------------------------------------------

const TYPE_META: Record<string, { icon: any; color: string; size: number; label: string }> = {
  domain: { icon: Globe, color: "#4A82F5", size: 42, label: "Domain" },
  subdomain: { icon: Server, color: "#06B6D4", size: 30, label: "Subdomain" },
  port: { icon: null, color: "#4A82F5", size: 18, label: "Port" },
  vulnerability: { icon: Bug, color: "#FB7185", size: 18, label: "Vulnerability" },
  certificate: { icon: ShieldAlert, color: "#F59E0B", size: 22, label: "Certificate" },
};

const SEVERITY_COLOR: Record<string, string> = {
  critical: "#FB7185",
  high: "#FF6B35",
  medium: "#F59E0B",
  low: "#06B6D4",
  unknown: "#818CF8",
};

const ALL_TYPES = Object.keys(TYPE_META);

// ---------------------------------------------------------------------------
// Cyberpunk node — circular with colored ring + glow
// ---------------------------------------------------------------------------

function CyberNode({ data, selected }: NodeProps) {
  const d = data as any;
  const meta = TYPE_META[d.type as string] || TYPE_META.subdomain;
  const Icon = meta.icon;
  const isVuln = d.type === "vulnerability";
  const sev = (d.severity as string) || "unknown";
  const isCritical = isVuln && (sev === "critical" || sev === "high");
  const dimmed = d.dimmed;
  const highlighted = d.highlighted;

  const ringColor = isVuln ? SEVERITY_COLOR[sev] || "#FB7185" : meta.color;

  return (
    <div
      className={cn(
        "relative flex items-center justify-center transition-all duration-200",
        dimmed && "opacity-10",
        highlighted && "opacity-100 scale-110"
      )}
      style={{ width: meta.size * 2, height: meta.size * 2 }}
    >
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />

      {/* Outer glow ring */}
      <span
        className="absolute rounded-full transition-all duration-300"
        style={{
          inset: -4,
          border: `1.5px solid ${ringColor}44`,
          boxShadow: selected
            ? `0 0 24px 4px ${ringColor}66`
            : isCritical
            ? `0 0 18px 2px ${ringColor}44`
            : `0 0 10px 1px ${ringColor}22`,
        }}
      />

      {/* Main circle */}
      <div
        className="relative flex items-center justify-center rounded-full transition-all duration-200"
        style={{
          width: meta.size * 2,
          height: meta.size * 2,
          background: `radial-gradient(circle at 30% 30%, ${ringColor}18, #0A0B0F 70%)`,
          border: `2px solid ${ringColor}`,
          boxShadow: `0 0 ${selected ? 20 : isCritical ? 14 : 8}px -2px ${ringColor}88, inset 0 0 20px ${ringColor}08`,
        }}
      >
        {Icon ? (
          <Icon
            style={{ width: meta.size * 0.45, height: meta.size * 0.45, color: ringColor }}
            className="relative z-10"
          />
        ) : (
          <span
            className="relative z-10 font-mono font-semibold"
            style={{ color: ringColor, fontSize: meta.size * 0.4 }}
          >
            {String(d.label).replace(":", "").slice(0, 6)}
          </span>
        )}
      </div>

      {/* Label below */}
      {d.showLabel && (
        <div
          className="absolute left-1/2 -translate-x-1/2 whitespace-nowrap rounded px-1.5 py-0.5 pointer-events-none z-20"
          style={{ top: meta.size * 2 + 4, background: "#0A0B0Fcc", border: `1px solid ${ringColor}33` }}
        >
          <span className="font-mono text-[9px]" style={{ color: ringColor }}>
            {d.label}
          </span>
        </div>
      )}
    </div>
  );
}

const nodeTypes = { domain: CyberNode, subdomain: CyberNode, port: CyberNode, vulnerability: CyberNode, certificate: CyberNode };

// ---------------------------------------------------------------------------
// Zone grouping — renders dashed-border boxes around grouped nodes
// ---------------------------------------------------------------------------

function ZoneOverlay({ nodes }: { nodes: Node[] }) {
  const zones = useMemo(() => {
    const groups: Record<string, { x: number; y: number; w: number; h: number; color: string; label: string }> = {};
    for (const n of nodes) {
      const zone = (n.data as any)?.zone;
      if (!zone) continue;
      if (!groups[zone]) {
        groups[zone] = { x: n.position.x - 80, y: n.position.y - 60, w: 160, h: 120, color: "#4A82F5", label: zone };
      }
      const g = groups[zone];
      g.x = Math.min(g.x, n.position.x - 80);
      g.y = Math.min(g.y, n.position.y - 60);
      g.w = Math.max(g.w, n.position.x + 80 - g.x);
      g.h = Math.max(g.h, n.position.y + 60 - g.y);
    }
    return Object.values(groups);
  }, [nodes]);

  if (zones.length === 0) return null;

  return (
    <div className="pointer-events-none absolute inset-0">
      {zones.map((z, i) => (
        <div
          key={i}
          className="absolute rounded-lg"
          style={{
            left: z.x,
            top: z.y,
            width: z.w,
            height: z.h,
            border: `1px dashed ${z.color}33`,
            background: `${z.color}05`,
          }}
        >
          <span
            className="absolute -top-3 left-3 text-[11px] uppercase tracking-wider px-1"
            style={{ color: `${z.color}88`, background: "#0A0B0F", border: `1px solid ${z.color}22` }}
          >
            [{z.label}]
          </span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// HEAT meter — bottom-left threat level indicator
// ---------------------------------------------------------------------------

function HeatMeter({ vulnCount, criticalCount }: { vulnCount: number; criticalCount: number }) {
  const heat = Math.min(10, Math.floor(criticalCount * 3 + vulnCount * 0.5));
  const heatColor = heat >= 7 ? "#FB7185" : heat >= 4 ? "#F59E0B" : "#4A82F5";
  const label = heat >= 7 ? "HIGH THREAT" : heat >= 4 ? "ELEVATED" : "SILENT";

  return (
    <div className="flex items-center gap-2 rounded border px-3 py-1.5" style={{ borderColor: `${heatColor}44`, background: "#0A0B0Fdd" }}>
      <span className=" text-[11px] font-semibold uppercase" style={{ color: heatColor }}>HEAT</span>
      <div className="flex gap-0.5">
        {Array.from({ length: 10 }, (_, i) => (
          <div
            key={i}
            className="h-2 w-1.5 rounded-sm transition-all duration-300"
            style={{
              background: i < heat ? heatColor : "#161B26",
              boxShadow: i < heat ? `0 0 4px ${heatColor}66` : "none",
            }}
          />
        ))}
      </div>
      <span className="font-mono text-[9px]" style={{ color: heatColor }}>{heat}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// NODE INTEL panel — right side detail panel
// ---------------------------------------------------------------------------

function NodeIntelPanel({ node, onClose }: { node: Node; onClose: () => void }) {
  const d = node.data as any;
  const type = d.type as string;
  const meta = TYPE_META[type] || TYPE_META.subdomain;
  const ringColor = type === "vulnerability" ? SEVERITY_COLOR[(d.severity as string) || "unknown"] : meta.color;
  const ports: any[] = Array.isArray(d.ports) ? d.ports : [];
  const osDetection: any = d.os_detection || d.attributes?.os_detection || null;
  const hostScripts: any[] = d.host_scripts || d.attributes?.host_scripts || [];

  return (
    <motion.div
      initial={{ x: 20, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 20, opacity: 0 }}
      className="absolute top-0 right-0 z-20 h-full w-72 border-l overflow-y-auto"
      style={{ borderColor: `${ringColor}33`, background: "#0A0B0Fee", backdropFilter: "blur(12px)" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: `${ringColor}22` }}>
        <div className="flex items-center gap-2">
          <span className=" text-[11px] font-semibold uppercase tracking-wider" style={{ color: "#4A82F5" }}>
            NODE INTEL
          </span>
        </div>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Status */}
      <div className="px-4 py-2 border-b" style={{ borderColor: "#161B26" }}>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] text-muted-foreground">STATUS</span>
          <span className="px-1.5 py-0.5 rounded font-mono text-[9px] font-semibold" style={{ background: `${ringColor}22`, color: ringColor }}>
            {d.severity?.toUpperCase() || "ACTIVE"}
          </span>
        </div>
      </div>

      {/* Node info */}
      <div className="px-4 py-3 space-y-3">
        <div>
          <span className=" text-[11px] text-muted-foreground uppercase">Type</span>
          <p className="font-mono text-xs mt-0.5" style={{ color: ringColor }}>{meta.label}</p>
        </div>
        <div>
          <span className=" text-[11px] text-muted-foreground uppercase">Label</span>
          <p className="font-mono text-xs mt-0.5 text-foreground">{d.label}</p>
        </div>
        {d.ips?.length > 0 && (
          <div>
            <span className=" text-[11px] text-muted-foreground uppercase">IPs</span>
            {d.ips.map((ip: string, i: number) => (
              <p key={i} className="font-mono text-xs mt-0.5 text-foreground/80">{ip}</p>
            ))}
          </div>
        )}
        {ports.length > 0 && (
          <div>
            <span className=" text-[11px] text-muted-foreground uppercase">Open Ports ({ports.length})</span>
            <div className="mt-1 space-y-1">
              {ports.slice(0, 20).map((p: any, i: number) => (
                <div key={i} className="flex items-center justify-between rounded px-2 py-1" style={{ background: "#161B26" }}>
                  <span className="font-mono text-[10px] text-foreground">{p.port}</span>
                  <span className="font-mono text-[9px] text-muted-foreground">{p.service || "?"}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        {osDetection && (
          <div>
            <span className=" text-[11px] text-muted-foreground uppercase">OS Detection</span>
            <div className="mt-1 rounded px-2 py-1" style={{ background: "#161B26" }}>
              {typeof osDetection === "string" ? (
                <p className="font-mono text-[10px] text-foreground">{osDetection}</p>
              ) : (
                <>
                  {osDetection.name && (
                    <p className="font-mono text-[10px] text-foreground">{osDetection.name}</p>
                  )}
                  {osDetection.accuracy && (
                    <p className="font-mono text-[9px] text-muted-foreground">Accuracy: {osDetection.accuracy}%</p>
                  )}
                  {osDetection.os_classes && osDetection.os_classes.length > 0 && (
                    <p className="font-mono text-[9px] text-muted-foreground">
                      {osDetection.os_classes.map((c: any) => `${c.type}/${c.vendor} ${c.osfamily} ${c.accuracy}%`).join(", ")}
                    </p>
                  )}
                </>
              )}
            </div>
          </div>
        )}
        {hostScripts.length > 0 && (
          <div>
            <span className=" text-[11px] text-muted-foreground uppercase">Host Scripts ({hostScripts.length})</span>
            <div className="mt-1 space-y-1">
              {hostScripts.slice(0, 5).map((s: any, i: number) => (
                <div key={i} className="rounded px-2 py-1" style={{ background: "#161B26" }}>
                  <p className="font-mono text-[10px] text-foreground">{s.id || s.name || "script"}</p>
                  {s.output && (
                    <p className="font-mono text-[9px] text-muted-foreground mt-0.5 break-all">{s.output.slice(0, 200)}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Graph canvas — core React Flow
// ---------------------------------------------------------------------------

function GraphCanvas({
  graphData,
  loading,
  typeFilters,
  searchTerm,
  highlightId,
  onNodeSelect,
  selectedNode,
}: {
  graphData: any;
  loading: boolean;
  typeFilters: Record<string, boolean>;
  searchTerm: string;
  highlightId: string | null;
  onNodeSelect: (node: Node | null) => void;
  selectedNode: Node | null;
}) {
  const { fitView, zoomTo, getNodes } = useReactFlow();
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const wrapRef = useRef<HTMLDivElement>(null);

  // Layout + filter
  useEffect(() => {
    if (!graphData?.nodes?.length) {
      setNodes([]);
      setEdges([]);
      return;
    }

    const filteredNodes = graphData.nodes.filter((n: any) => typeFilters[n.type] !== false);
    const filteredIds = new Set(filteredNodes.map((n: any) => n.id));

    const rawNodes: RawGraphNode[] = filteredNodes.map((n: any) => ({
      id: n.id, label: n.label, type: n.type, ips: n.ips, ports: n.ports,
      severity: n.severity, zone: n.zone,
    }));
    const rawEdges: RawGraphEdge[] = (graphData.edges || [])
      .filter((e: any) => filteredIds.has(e.source) && filteredIds.has(e.target))
      .map((e: any) => ({ source: e.source, target: e.target, label: e.label }));

    const layout = computeForceLayout(rawNodes, rawEdges);

    const flowNodes: Node[] = rawNodes.map((n) => {
      const pos = layout.positions.get(n.id) || { x: 0, y: 0 };
      const isHighlighted = highlightId === n.id || n.id.includes(searchTerm.toLowerCase());
      return {
        id: n.id, type: n.type, position: pos,
        data: {
          ...n,
          showLabel: n.type === "domain" || n.type === "vulnerability" || n.type === "certificate",
          dimmed: highlightId ? !isHighlighted : false,
          highlighted: isHighlighted,
        },
      };
    });

    const edgeColors: Record<string, string> = { attack: "#FB7185", "weak-cipher": "#F59E0B" };

    const flowEdges: Edge[] = rawEdges.map((e, i) => ({
      id: `e-${i}`, source: e.source, target: e.target,
      type: "smoothstep",
      animated: e.label === "attack",
      style: {
        stroke: edgeColors[e.label || ""] || "#4A82F555",
        strokeWidth: e.label === "attack" ? 2 : 1,
        strokeDasharray: e.label === "attack" ? "6 3" : undefined,
      },
      markerEnd: { type: MarkerType.ArrowClosed, color: edgeColors[e.label || ""] || "#4A82F555", width: 12, height: 12 },
    }));

    setNodes(flowNodes);
    setEdges(flowEdges);

    setTimeout(() => fitView({ padding: 0.15, duration: 400 }), 50);
  }, [graphData, typeFilters, highlightId, searchTerm, fitView, setNodes, setEdges]);

  const onNodeClick = useCallback((_: any, node: Node) => {
    onNodeSelect(node);
  }, [onNodeSelect]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-6 w-6 animate-spin" style={{ color: "#4A82F5" }} />
          <p className="font-mono text-xs" style={{ color: "#4A82F588" }}>Computing attack graph...</p>
        </div>
      </div>
    );
  }

  if (!graphData || !graphData.nodes?.length) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center space-y-3">
          <Waypoints className="h-10 w-10 mx-auto" style={{ color: "#161B26" }} />
          <p className="font-mono text-xs text-muted-foreground">No graph data available</p>
        </div>
      </div>
    );
  }

  return (
    <div ref={wrapRef} className="relative h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        minZoom={0.05}
        maxZoom={3}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        proOptions={{ hideAttribution: true }}
        className="bg-transparent"
      >
        <Background variant={BackgroundVariant.Dots} gap={40} size={1} color="#161B2644" />
        <Controls
          showZoom
          showFitView
          showInteractive={false}
          className="!rounded !border !bg-[#0A0B0Fdd] !"
          style={{ borderColor: "#161B26", background: "#0A0B0Fdd" }}
        />
      </ReactFlow>

      <AnimatePresence>
        {selectedNode && <NodeIntelPanel node={selectedNode} onClose={() => onNodeSelect(null)} />}
      </AnimatePresence>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

function GraphContent() {
  const { markComplete } = useChecklistAutoComplete();
  const [scans, setScans] = useState<Scan[]>([]);
  const [selectedScanId, setSelectedScanId] = useState<string>("");
  const [loadingScans, setLoadingScans] = useState(true);
  const [graphData, setGraphData] = useState<any>(null);
  const [loadingGraph, setLoadingGraph] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [typeFilters, setTypeFilters] = useState<Record<string, boolean>>({
    domain: true, subdomain: true, port: true, vulnerability: true, certificate: true,
  });
  const [search, setSearch] = useState("");
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);

  useEffect(() => {
    listScans({ limit: 100 })
      .then((data) => {
        const completed = data.filter((s) => s.status === "completed");
        setScans(completed);
        if (completed.length > 0) setSelectedScanId(completed[0].id);
      })
      .catch(() => setError("Failed to load scans"))
      .finally(() => setLoadingScans(false));
  }, []);

  const fetchGraph = useCallback(async (scanId: string) => {
    if (!scanId) return;
    setLoadingGraph(true);
    setError(null);
    setGraphData(null);
    try {
      const data = await getAssetGraph(scanId);
      setGraphData(data);
      markComplete("attack_graph");
    } catch {
      setError("Failed to load graph data");
    } finally {
      setLoadingGraph(false);
    }
  }, []);

  useEffect(() => {
    if (selectedScanId) fetchGraph(selectedScanId);
  }, [selectedScanId, fetchGraph]);

  const nodeStats = useMemo(() => {
    if (!graphData) return { total: 0, domains: 0, subdomains: 0, vulns: 0, critical: 0 };
    const nodes = graphData.nodes || [];
    return {
      total: nodes.length,
      domains: nodes.filter((n: any) => n.type === "domain").length,
      subdomains: nodes.filter((n: any) => n.type === "subdomain").length,
      vulns: nodes.filter((n: any) => n.type === "vulnerability").length,
      critical: nodes.filter((n: any) => n.type === "vulnerability" && (n.severity === "critical" || n.severity === "high")).length,
    };
  }, [graphData]);

  const toggleType = (t: string) => setTypeFilters((prev) => ({ ...prev, [t]: !prev[t] }));

  const matchNode = useMemo(() => {
    if (!search.trim() || !graphData) return null;
    const q = search.trim().toLowerCase();
    const found = graphData.nodes.find((n: any) => n.label?.toLowerCase().includes(q) || n.id.toLowerCase().includes(q));
    return found ? found.id : null;
  }, [search, graphData]);

  const threatLabel = nodeStats.critical > 0 ? `${nodeStats.critical} THREATS` : "No threats detected";

  return (
    <div className="flex h-screen flex-col overflow-hidden" style={{ background: "#050608" }}>
      {/* ── Status bar (top) ── */}
      <div className="shrink-0 border-b px-6 py-2 flex items-center justify-between" style={{ borderColor: "#161B26", background: "#0A0B0Fee" }}>
        <div className="flex items-center gap-4">
          {/* Scan selector */}
          <select
            value={selectedScanId}
            onChange={(e) => setSelectedScanId(e.target.value)}
            disabled={loadingScans}
            className="h-7 rounded border px-2 text-[11px] font-mono focus:outline-none"
            style={{ borderColor: "#161B26", background: "#0D1117", color: "#4A82F5" }}
          >
            {loadingScans && <option>Loading...</option>}
            {!loadingScans && scans.length === 0 && <option>No scans</option>}
            {scans.map((scan) => (
              <option key={scan.id} value={scan.id}>{scan.domain}</option>
            ))}
          </select>

          {/* Threat status */}
          <div className="flex items-center gap-2">
            <span
              className=" text-[11px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded"
              style={{
                color: nodeStats.critical > 0 ? "#FB7185" : "#4A82F5",
                background: nodeStats.critical > 0 ? "#FB718515" : "#4A82F515",
                border: `1px solid ${nodeStats.critical > 0 ? "#FB718533" : "#4A82F533"}`,
              }}
            >
              {nodeStats.critical > 0 ? "ALERT" : "SILENT"}
            </span>
            <span className="font-mono text-[10px] text-muted-foreground">{threatLabel}</span>
          </div>
        </div>

        {/* Search */}
        <form
          onSubmit={(e) => { e.preventDefault(); setHighlightId(matchNode); }}
          className="flex items-center gap-1.5 rounded border px-2 py-1"
          style={{ borderColor: "#161B26", background: "#0D1117" }}
        >
          <Search className="h-3 w-3" style={{ color: "#4A82F566" }} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search nodes..."
            className="h-5 w-32 bg-transparent text-[10px] font-mono focus:outline-none"
            style={{ color: "#4A82F5" }}
          />
          {search.trim() && (
            <span className="font-mono text-[9px]" style={{ color: matchNode ? "#4A82F5" : "#FB718566" }}>
              {matchNode ? "found" : "—"}
            </span>
          )}
        </form>
      </div>

      {/* ── Main area ── */}
      <div className="relative flex-1 overflow-hidden">
        {/* Filter toggles (left) */}
        {graphData && !loadingGraph && (
          <div className="absolute top-3 left-3 z-10 flex flex-col gap-1.5 rounded border p-2" style={{ borderColor: "#161B26", background: "#0A0B0Fee", backdropFilter: "blur(8px)" }}>
            <span className=" text-[11px] text-muted-foreground uppercase mb-1">Types</span>
            {ALL_TYPES.map((t) => {
              const m = TYPE_META[t];
              const on = typeFilters[t];
              return (
                <button
                  key={t}
                  onClick={() => toggleType(t)}
                  className={cn(
                    "flex items-center gap-1.5 rounded px-2 py-1 text-[10px] font-mono transition-all",
                    on ? "opacity-100" : "opacity-30"
                  )}
                  style={{ background: on ? `${m.color}11` : "transparent" }}
                >
                  <span className="h-2 w-2 rounded-full" style={{ background: m.color, boxShadow: on ? `0 0 6px ${m.color}66` : "none" }} />
                  {m.label}
                </button>
              );
            })}
          </div>
        )}

        {/* HEAT meter (bottom-left) */}
        {graphData && !loadingGraph && (
          <div className="absolute bottom-3 left-3 z-10">
            <HeatMeter vulnCount={nodeStats.vulns} criticalCount={nodeStats.critical} />
          </div>
        )}

        {/* Node stats (bottom-center) */}
        {graphData && !loadingGraph && (
          <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-10 flex items-center gap-4 rounded border px-4 py-1.5" style={{ borderColor: "#161B26", background: "#0A0B0Fee" }}>
            <span className="font-mono text-[10px] text-muted-foreground">
              Nodes: <span className="text-foreground">{nodeStats.total}</span>
            </span>
            <span className="font-mono text-[10px]" style={{ color: "#4A82F5" }}>
              {nodeStats.domains} domains
            </span>
            <span className="font-mono text-[10px]" style={{ color: "#06B6D4" }}>
              {nodeStats.subdomains} subdomains
            </span>
          </div>
        )}

        {/* Graph */}
        {error ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center space-y-3">
              <Bug className="h-8 w-8 mx-auto" style={{ color: "#FB7185" }} />
              <p className="font-mono text-xs" style={{ color: "#FB7185" }}>{error}</p>
              <Button variant="outline" size="sm" onClick={() => selectedScanId && fetchGraph(selectedScanId)} className="gap-1.5" style={{ borderColor: "#161B26" }}>
                Retry
              </Button>
            </div>
          </div>
        ) : (
          <ReactFlowProvider>
            <GraphCanvas
              graphData={graphData}
              loading={loadingGraph}
              typeFilters={typeFilters}
              searchTerm={search}
              highlightId={highlightId}
              onNodeSelect={setSelectedNode}
              selectedNode={selectedNode}
            />
          </ReactFlowProvider>
        )}
      </div>
    </div>
  );
}

export default function GraphPage() {
  return (
    <ProtectedRoute>
      <GraphContent />
    </ProtectedRoute>
  );
}
