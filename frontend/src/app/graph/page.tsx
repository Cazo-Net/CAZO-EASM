"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { listScans, getAssetGraph } from "@/lib/api";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  Waypoints,
  Globe,
  Server,
  Bug,
  Loader2,
  ZoomIn,
  ZoomOut,
  Maximize,
  RefreshCw,
} from "lucide-react";
import { motion } from "framer-motion";
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  MarkerType,
  Position,
  Handle,
} from "reactflow";
import "reactflow/dist/style.css";
import type { Scan } from "@/types";

interface GraphNode {
  id: string;
  label: string;
  type: "domain" | "subdomain" | "port" | "vulnerability";
  ips?: string[];
  service?: string;
  severity?: string;
}

interface GraphData {
  nodes: GraphNode[];
  edges: { source: string; target: string }[];
}

const SEVERITY_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  critical: { bg: "bg-red-500/20", border: "border-red-500/50", text: "text-red-400" },
  high: { bg: "bg-orange-500/20", border: "border-orange-500/50", text: "text-orange-400" },
  medium: { bg: "bg-amber-500/20", border: "border-amber-500/50", text: "text-amber-400" },
  low: { bg: "bg-yellow-500/20", border: "border-yellow-500/50", text: "text-yellow-400" },
  unknown: { bg: "bg-zinc-500/20", border: "border-zinc-500/50", text: "text-zinc-400" },
};

function getSeverityColor(severity?: string) {
  return SEVERITY_COLORS[severity || "unknown"] || SEVERITY_COLORS.unknown;
}

// --- Custom Node Components ---

function DomainNode({ data }: { data: { label: string } }) {
  return (
    <div className="group relative flex items-center justify-center">
      <Handle type="target" position={Position.Top} className="!bg-primary !border-primary" />
      <div
        className={cn(
          "relative flex h-20 w-20 items-center justify-center rounded-full",
          "bg-gradient-to-br from-primary to-blue-400",
          "shadow-lg shadow-primary/30",
          "border-2 border-primary/60",
          "transition-all duration-300 group-hover:shadow-xl group-hover:shadow-primary/40 group-hover:scale-110"
        )}
      >
        <div className="absolute inset-0 rounded-full bg-primary/20 blur-xl" />
        <Globe className="relative z-10 h-8 w-8 text-white" />
      </div>
      <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 whitespace-nowrap">
        <span className="text-xs font-semibold text-primary">{data.label}</span>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-primary !border-primary" />
    </div>
  );
}

function SubdomainNode({ data }: { data: { label: string; ips?: string[] } }) {
  return (
    <div className="group relative flex items-center justify-center">
      <Handle type="target" position={Position.Top} className="!bg-cyan-400 !border-cyan-400" />
      <div
        className={cn(
          "relative flex h-14 w-14 items-center justify-center rounded-full",
          "bg-gradient-to-br from-cyan-500 to-cyan-400",
          "shadow-md shadow-cyan-500/20",
          "border-2 border-cyan-400/50",
          "transition-all duration-300 group-hover:shadow-lg group-hover:shadow-cyan-400/30 group-hover:scale-110"
        )}
      >
        <Server className="relative z-10 h-5 w-5 text-white" />
      </div>
      <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 whitespace-nowrap">
        <span className="text-[10px] font-medium text-cyan-400">{data.label}</span>
        {data.ips && data.ips.length > 0 && (
          <p className="text-[9px] text-muted-foreground text-center">{data.ips[0]}</p>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-cyan-400 !border-cyan-400" />
    </div>
  );
}

function PortNode({ data }: { data: { label: string; service?: string } }) {
  return (
    <div className="group relative flex items-center justify-center">
      <Handle type="target" position={Position.Top} className="!bg-emerald-400 !border-emerald-400" />
      <div
        className={cn(
          "relative flex h-9 items-center justify-center gap-1.5 rounded-lg px-3",
          "bg-gradient-to-br from-emerald-500/20 to-emerald-400/10",
          "border border-emerald-500/40",
          "transition-all duration-300 group-hover:border-emerald-400/60 group-hover:shadow-md group-hover:shadow-emerald-500/20"
        )}
      >
        <span className="text-xs font-bold text-emerald-400">{data.label}</span>
      </div>
      {data.service && (
        <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 whitespace-nowrap">
          <span className="text-[9px] text-emerald-400/70">{data.service}</span>
        </div>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-emerald-400 !border-emerald-400" />
    </div>
  );
}

function VulnerabilityNode({ data }: { data: { label: string; severity?: string } }) {
  const colors = getSeverityColor(data.severity);
  return (
    <div className="group relative flex items-center justify-center">
      <Handle type="target" position={Position.Top} className={cn("!border-current", colors.text)} />
      <div
        className={cn(
          "relative flex h-10 w-10 rotate-45 items-center justify-center",
          colors.bg,
          "border",
          colors.border,
          "transition-all duration-300 group-hover:scale-110"
        )}
      >
        <Bug className={cn("relative z-10 -rotate-45 h-4 w-4", colors.text)} />
      </div>
      <div className="absolute -bottom-7 left-1/2 -translate-x-1/2 whitespace-nowrap">
        <span className={cn("text-[9px] font-semibold", colors.text)}>{data.label}</span>
        {data.severity && (
          <Badge variant="destructive" className="ml-1 text-[8px] px-1 py-0 capitalize">
            {data.severity}
          </Badge>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} className={cn("!border-current", colors.text)} />
    </div>
  );
}

const nodeTypes = {
  domain: DomainNode,
  subdomain: SubdomainNode,
  port: PortNode,
  vulnerability: VulnerabilityNode,
};

// --- Layout Algorithm ---

function layoutGraph(rawNodes: GraphNode[], rawEdges: { source: string; target: string }[]) {
  const nodeMap = new Map(rawNodes.map((n) => [n.id, n]));
  const childrenMap = new Map<string, string[]>();
  const nodeCount = rawNodes.length;

  rawEdges.forEach((e) => {
    if (!childrenMap.has(e.source)) childrenMap.set(e.source, []);
    childrenMap.get(e.source)!.push(e.target);
  });

  const domainNodes = rawNodes.filter((n) => n.type === "domain");
  const subdomainNodes = rawNodes.filter((n) => n.type === "subdomain");
  const portNodes = rawNodes.filter((n) => n.type === "port");
  const vulnNodes = rawNodes.filter((n) => n.type === "vulnerability");

  const LEVEL_Y: Record<string, number> = {
    domain: 50,
    subdomain: 200,
    port: 380,
    vulnerability: 520,
  };

  const NODE_W: Record<string, number> = {
    domain: 120,
    subdomain: 100,
    port: 80,
    vulnerability: 70,
  };

  const layoutedNodes: Node[] = [];

  const placeRow = (nodes: GraphNode[], y: number, parentX?: number) => {
    if (nodes.length === 0) return;
    const totalWidth = nodes.reduce((sum, n) => sum + NODE_W[n.type], 0) + (nodes.length - 1) * 40;
    let startX = parentX !== undefined ? parentX - totalWidth / 2 : -(totalWidth / 2);

    nodes.forEach((n) => {
      const w = NODE_W[n.type];
      layoutedNodes.push({
        id: n.id,
        type: n.type,
        position: { x: startX + w / 2, y },
        data: { label: n.label, ips: n.ips, service: n.service, severity: n.severity },
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
      });
      startX += w + 40;
    });
  };

  if (nodeCount <= 1) {
    placeRow(rawNodes, 50);
    return { nodes: layoutedNodes, edges: rawEdges };
  }

  if (domainNodes.length > 0) {
    const totalDomainWidth = domainNodes.length * NODE_W.domain + (domainNodes.length - 1) * 60;
    let dx = -(totalDomainWidth / 2);
    domainNodes.forEach((dn) => {
      const children = (childrenMap.get(dn.id) || [])
        .map((cid) => nodeMap.get(cid))
        .filter(Boolean) as GraphNode[];
      const subs = children.filter((c) => c.type === "subdomain");
      const placedChildrenWidth =
        subs.length > 0
          ? subs.reduce((s, c) => s + NODE_W[c.type], 0) + (subs.length - 1) * 40
          : 0;
      const centerX = dx + NODE_W.domain / 2;

      layoutedNodes.push({
        id: dn.id,
        type: dn.type,
        position: { x: centerX, y: LEVEL_Y.domain },
        data: { label: dn.label },
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
      });

      if (subs.length > 0) {
        placeRow(subs, LEVEL_Y.subdomain, centerX);
        subs.forEach((sub) => {
          const grandchildren = (childrenMap.get(sub.id) || [])
            .map((cid) => nodeMap.get(cid))
            .filter(Boolean) as GraphNode[];
          const ports = grandchildren.filter((c) => c.type === "port");
          const vulns = grandchildren.filter((c) => c.type === "vulnerability");
          const subX = layoutedNodes.find((n) => n.id === sub.id)?.position.x || 0;

          if (ports.length > 0) placeRow(ports, LEVEL_Y.port, subX);
          ports.forEach((port) => {
            const greatGrandchildren = (childrenMap.get(port.id) || [])
              .map((cid) => nodeMap.get(cid))
              .filter(Boolean) as GraphNode[];
            const portVulns = greatGrandchildren.filter((c) => c.type === "vulnerability");
            if (portVulns.length > 0) {
              const portX = layoutedNodes.find((n) => n.id === port.id)?.position.x || 0;
              placeRow(portVulns, LEVEL_Y.vulnerability, portX);
            }
          });

          if (vulns.length > 0 && ports.length === 0) {
            placeRow(vulns, LEVEL_Y.vulnerability, subX);
          }
        });
      }

      dx += NODE_W.domain + 60;
    });

    // Place orphan nodes (not connected to any domain)
    const placedIds = new Set(layoutedNodes.map((n) => n.id));
    const orphans = rawNodes.filter((n) => !placedIds.has(n.id));
    if (orphans.length > 0) {
      placeRow(orphans, LEVEL_Y.subdomain);
    }
  } else {
    // No domain nodes, flat layout
    placeRow(subdomainNodes, 50);
    placeRow(portNodes, 200);
    placeRow(vulnNodes, 350);
  }

  return { nodes: layoutedNodes, edges: rawEdges };
}

// --- Legend ---

function GraphLegend() {
  const items = [
    { label: "Domain", icon: Globe, color: "from-primary to-blue-400", shape: "rounded-full" },
    { label: "Subdomain", icon: Server, color: "from-cyan-500 to-cyan-400", shape: "rounded-full" },
    { label: "Port", icon: null, color: "from-emerald-500/20 to-emerald-400/10", shape: "rounded-lg" },
    { label: "Vulnerability", icon: Bug, color: "bg-red-500/20", shape: "rotate-45" },
  ];

  return (
    <div className="absolute bottom-4 left-4 z-10 glass rounded-xl p-3 space-y-2">
      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">Legend</p>
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-2">
          {item.label === "Port" ? (
            <div className={cn("flex h-5 items-center justify-center rounded-md border border-emerald-500/40 bg-gradient-to-br from-emerald-500/20 to-emerald-400/10 px-1.5")}>
              <span className="text-[8px] font-bold text-emerald-400">80</span>
            </div>
          ) : (
            <div
              className={cn(
                "flex h-6 w-6 items-center justify-center",
                item.shape,
                item.color.includes("rotate") ? "" : `bg-gradient-to-br ${item.color}`
              )}
            >
              {item.icon && <item.icon className={cn("h-3 w-3", item.color.includes("bg-red") ? "text-red-400" : "text-white")} />}
              {item.label === "Vulnerability" && <Bug className="relative z-10 -rotate-45 h-3 w-3 text-red-400" />}
            </div>
          )}
          <span className="text-[10px] text-muted-foreground">{item.label}</span>
        </div>
      ))}
    </div>
  );
}

// --- Main Page ---

function GraphContent() {
  const [scans, setScans] = useState<Scan[]>([]);
  const [selectedScanId, setSelectedScanId] = useState<string>("");
  const [loadingScans, setLoadingScans] = useState(true);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loadingGraph, setLoadingGraph] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

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
      const data: GraphData = await getAssetGraph(scanId);
      setGraphData(data);

      if (!data.nodes || data.nodes.length === 0) {
        setNodes([]);
        setEdges([]);
        return;
      }

      const { nodes: layouted, edges: layoutedEdges } = layoutGraph(data.nodes, data.edges);

      const flowEdges: Edge[] = layoutedEdges.map((e, i) => ({
        id: `e-${e.source}-${e.target}-${i}`,
        source: e.source,
        target: e.target,
        type: "smoothstep",
        animated: true,
        style: { stroke: "#2563EB", strokeWidth: 1.5, opacity: 0.6 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: "#2563EB",
          width: 12,
          height: 12,
        },
      }));

      setNodes(layouted);
      setEdges(flowEdges);
    } catch {
      setError("Failed to load graph data");
      setNodes([]);
      setEdges([]);
    } finally {
      setLoadingGraph(false);
    }
  }, [setNodes, setEdges]);

  useEffect(() => {
    if (selectedScanId) fetchGraph(selectedScanId);
  }, [selectedScanId, fetchGraph]);

  const selectedScan = useMemo(() => scans.find((s) => s.id === selectedScanId), [scans, selectedScanId]);

  const nodeStats = useMemo(() => {
    if (!graphData) return { total: 0, domains: 0, subdomains: 0, ports: 0, vulns: 0 };
    return {
      total: graphData.nodes.length,
      domains: graphData.nodes.filter((n) => n.type === "domain").length,
      subdomains: graphData.nodes.filter((n) => n.type === "subdomain").length,
      ports: graphData.nodes.filter((n) => n.type === "port").length,
      vulns: graphData.nodes.filter((n) => n.type === "vulnerability").length,
    };
  }, [graphData]);

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {/* Header */}
      <div className="border-b border-border/50 bg-card/30 backdrop-blur-xl z-20 shrink-0">
        <div className="mx-auto max-w-full px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 border border-primary/20">
                <Waypoints className="h-5 w-5 text-primary" />
              </div>
              <div>
                <h1 className="text-lg font-bold tracking-tight">Attack Graph</h1>
                <p className="text-xs text-muted-foreground">
                  Interactive visualization of discovered assets and vulnerabilities
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Scan Selector */}
              <div className="flex items-center gap-2">
                <label className="text-xs text-muted-foreground">Scan:</label>
                <select
                  value={selectedScanId}
                  onChange={(e) => setSelectedScanId(e.target.value)}
                  disabled={loadingScans}
                  className="h-9 rounded-lg border border-border/50 bg-muted/30 px-3 text-sm focus:border-primary/50 focus:outline-none transition-colors min-w-[200px]"
                >
                  {loadingScans && <option>Loading scans...</option>}
                  {!loadingScans && scans.length === 0 && <option>No completed scans</option>}
                  {scans.map((scan) => (
                    <option key={scan.id} value={scan.id}>
                      {scan.domain} ({scan.scan_type})
                    </option>
                  ))}
                </select>
              </div>

              <Button
                variant="outline"
                size="sm"
                onClick={() => selectedScanId && fetchGraph(selectedScanId)}
                disabled={!selectedScanId || loadingGraph}
                className="gap-1.5 border-border/50"
              >
                <RefreshCw className={cn("h-3.5 w-3.5", loadingGraph && "animate-spin")} />
                Refresh
              </Button>
            </div>
          </div>

          {/* Stats bar */}
          {graphData && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-4 mt-3"
            >
              {[
                { label: "Total Nodes", value: nodeStats.total, color: "text-foreground" },
                { label: "Domains", value: nodeStats.domains, color: "text-primary" },
                { label: "Subdomains", value: nodeStats.subdomains, color: "text-cyan-400" },
                { label: "Ports", value: nodeStats.ports, color: "text-emerald-400" },
                { label: "Vulnerabilities", value: nodeStats.vulns, color: "text-red-400" },
              ].map((stat) => (
                <div key={stat.label} className="flex items-center gap-1.5 text-xs">
                  <span className="text-muted-foreground">{stat.label}:</span>
                  <span className={cn("font-semibold", stat.color)}>{stat.value}</span>
                </div>
              ))}
            </motion.div>
          )}
        </div>
      </div>

      {/* Graph Area */}
      <div className="relative flex-1 bg-background">
        {loadingGraph ? (
          <div className="flex h-full items-center justify-center">
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <p className="text-sm text-muted-foreground">Loading attack graph...</p>
            </div>
          </div>
        ) : error ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center space-y-3">
              <Bug className="h-10 w-10 text-destructive mx-auto" />
              <p className="text-sm text-destructive font-medium">{error}</p>
              <Button variant="outline" size="sm" onClick={() => selectedScanId && fetchGraph(selectedScanId)} className="gap-1.5">
                <RefreshCw className="h-3.5 w-3.5" />
                Retry
              </Button>
            </div>
          </div>
        ) : nodes.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center space-y-3">
              <div className="relative inline-block">
                <div className="absolute inset-0 bg-primary/10 rounded-full blur-xl" />
                <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-muted/50 border border-border/30 mx-auto">
                  <Waypoints className="h-8 w-8 text-muted-foreground" />
                </div>
              </div>
              <div>
                <h3 className="text-sm font-semibold">No graph data</h3>
                <p className="text-xs text-muted-foreground mt-1 max-w-xs">
                  {selectedScanId ? "This scan has no discoverable assets to graph." : "Select a scan to view its attack graph."}
                </p>
              </div>
            </div>
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.1}
            maxZoom={2}
            proOptions={{ hideAttribution: true }}
            className="bg-background"
          >
            <Background
              variant={BackgroundVariant.Dots}
              gap={24}
              size={1}
              color="rgba(255,255,255,0.04)"
            />
            <Controls
              showZoom={true}
              showFitView={true}
              showInteractive={false}
              className="!bg-card/80 !backdrop-blur-xl !border-border/50 !shadow-lg"
            />
          </ReactFlow>
        )}

        {/* Legend */}
        {nodes.length > 0 && <GraphLegend />}

        {/* Scan info overlay */}
        {selectedScan && !loadingGraph && (
          <div className="absolute top-4 right-4 z-10 glass rounded-xl p-3 max-w-[200px]">
            <p className="text-[10px] text-muted-foreground">Active Scan</p>
            <p className="text-xs font-semibold text-foreground truncate">{selectedScan.domain}</p>
            <p className="text-[10px] text-muted-foreground mt-0.5">
              {new Date(selectedScan.created_at).toLocaleDateString()}
            </p>
          </div>
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
