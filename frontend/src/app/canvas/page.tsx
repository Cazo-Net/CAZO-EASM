"use client";

import { useCallback, useState, useEffect, useRef, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  BackgroundVariant,
  type Connection,
  type Edge,
  type Node,
  type NodeTypes,
  type OnNodesChange,
  type OnConnect,
  Panel,
  useReactFlow,
  ReactFlowProvider,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Loader2,
  Plus,
  Save,
  Trash2,
  Download,
  Upload,
  Search,
  Filter,
  Eye,
  EyeOff,
  Lock,
  Unlock,
  Tag,
  MessageSquare,
  Palette,
  X,
  ChevronDown,
  ChevronRight,
  Globe,
  Server,
  Lock as LockIcon,
  Network,
  Cpu,
  Bug,
  Building,
  Mail,
  Cloud,
  ExternalLink,
  FileText,
  Settings,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import {
  listCanvases,
  getCanvas,
  createCanvas,
  updateCanvas,
  deleteCanvas,
  updateCanvasNode,
  deleteCanvasNode,
  addCanvasEdge,
  deleteCanvasEdge,
  importScanToCanvas,
  exportCanvas,
  listImportableScans,
  previewScanAssets,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import type { Canvas as CanvasType, CanvasNode, CanvasEdge, CanvasDetail, Scan } from "@/types";

const ASSET_TYPE_CONFIG: Record<string, { icon: any; color: string; label: string }> = {
  domain: { icon: Globe, color: "#3B82F6", label: "Domain" },
  subdomain: { icon: Globe, color: "#06B6D4", label: "Subdomain" },
  ip_address: { icon: Server, color: "#8B5CF6", label: "IP Address" },
  port: { icon: Server, color: "#EC4899", label: "Port" },
  ssl_certificate: { icon: LockIcon, color: "#10B981", label: "SSL Certificate" },
  dns_record: { icon: Network, color: "#F59E0B", label: "DNS Record" },
  technology: { icon: Cpu, color: "#8B5CF6", label: "Technology" },
  vulnerability: { icon: Bug, color: "#EF4444", label: "Vulnerability" },
  organization: { icon: Building, color: "#6366F1", label: "Organization" },
  email: { icon: Mail, color: "#EC4899", label: "Email" },
  cloud_asset: { icon: Cloud, color: "#06B6D4", label: "Cloud Asset" },
  web_application: { icon: Globe, color: "#3B82F6", label: "Web App" },
  external_service: { icon: ExternalLink, color: "#F97316", label: "External Service" },
  note: { icon: FileText, color: "#6B7280", label: "Note" },
};

const RISK_COLORS: Record<string, string> = {
  critical: "#EF4444",
  high: "#F97316",
  medium: "#F59E0B",
  low: "#3B82F6",
  informational: "#6B7280",
};

function AssetNode({ data }: { data: any }) {
  const config = ASSET_TYPE_CONFIG[data.asset_type] || ASSET_TYPE_CONFIG.note;
  const Icon = config.icon;
  const riskColor = RISK_COLORS[data.risk_level] || "#6B7280";

  return (
    <div
      className={cn(
        "rounded-xl border bg-card/90 backdrop-blur-sm shadow-lg transition-all hover:shadow-xl hover:border-primary/30",
        data.selected && "border-primary ring-2 ring-primary/20"
      )}
      style={{ width: data.width || 200, borderColor: riskColor + "40" }}
    >
      <div
        className="flex items-center gap-2 rounded-t-xl px-3 py-2"
        style={{ backgroundColor: riskColor + "15" }}
      >
        <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md" style={{ backgroundColor: config.color + "20" }}>
          <Icon className="h-3.5 w-3.5" style={{ color: config.color }} />
        </div>
        <span className="text-xs font-semibold truncate flex-1">{data.label}</span>
        <div className="h-2 w-2 rounded-full" style={{ backgroundColor: riskColor }} />
      </div>
      <div className="px-3 py-2">
        <p className="text-[10px] text-muted-foreground">{config.label}</p>
        {data.notes && <p className="text-[10px] text-muted-foreground mt-1 line-clamp-2">{data.notes}</p>}
        {data.tags && data.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1.5">
            {data.tags.slice(0, 3).map((tag: string) => (
              <span key={tag} className="rounded-full bg-primary/10 px-1.5 py-0.5 text-[8px] text-primary">{tag}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

const nodeTypes: NodeTypes = { asset: AssetNode as any };

function CanvasContent() {
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const { fitView } = useReactFlow();

  const [canvases, setCanvases] = useState<CanvasType[]>([]);
  const [activeCanvas, setActiveCanvas] = useState<CanvasDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showSidebar, setShowSidebar] = useState(true);
  const [showAssetPanel, setShowAssetPanel] = useState(false);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState<string>("");
  const [filterRisk, setFilterRisk] = useState<string>("");
  const [showImportModal, setShowImportModal] = useState(false);
  const [scans, setScans] = useState<Scan[]>([]);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  useEffect(() => {
    loadCanvases();
  }, []);

  useEffect(() => {
    if (activeCanvas) {
      const rfNodes: Node[] = activeCanvas.nodes
        .filter((n) => !n.hidden)
        .map((n) => ({
          id: n.id,
          type: "asset",
          position: { x: n.x, y: n.y },
          data: {
            label: n.label,
            asset_type: n.asset_type,
            asset_id: n.asset_id,
            risk_level: n.risk_level,
            notes: n.notes,
            tags: n.tags,
            width: n.width,
            height: n.height,
            color: n.color,
            canvas_node_id: n.id,
          },
          style: { width: n.width || 200 },
        }));
      const rfEdges: Edge[] = activeCanvas.edges.map((e) => ({
        id: e.id,
        source: e.source_node_id,
        target: e.target_node_id,
        label: e.label,
        type: "default",
        animated: e.animated,
        style: { stroke: "#3B82F6", strokeWidth: 1.5 },
      }));
      setNodes(rfNodes);
      setEdges(rfEdges);
    }
  }, [activeCanvas]);

  const loadCanvases = async () => {
    setLoading(true);
    try {
      const data = await listCanvases();
      setCanvases(data);
      if (data.length > 0) {
        await loadCanvas(data[0].id);
      }
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  };

  const loadCanvas = async (id: string) => {
    try {
      const data: CanvasDetail = await getCanvas(id);
      setActiveCanvas(data);
    } catch {
      // silently fail
    }
  };

  const handleCreateCanvas = async () => {
    try {
      const canvas = await createCanvas({ name: `Canvas ${canvases.length + 1}` });
      setCanvases((prev) => [canvas, ...prev]);
      await loadCanvas(canvas.id);
    } catch {
      // silently fail
    }
  };

  const handleDeleteCanvas = async (id: string) => {
    try {
      await deleteCanvas(id);
      setCanvases((prev) => prev.filter((c) => c.id !== id));
      if (activeCanvas?.id === id) {
        setActiveCanvas(null);
        setNodes([]);
        setEdges([]);
      }
    } catch {
      // silently fail
    }
  };

  const handleSave = async () => {
    if (!activeCanvas) return;
    setSaving(true);
    try {
      const nodesData = nodes.map((n) => ({
        id: n.data.canvas_node_id as string,
        x: n.position.x,
        y: n.position.y,
      }));
      for (const nd of nodesData) {
        if (nd.id) {
          await updateCanvasNode(activeCanvas.id, nd.id, { x: nd.x, y: nd.y });
        }
      }
    } catch {
      // silently fail
    } finally {
      setSaving(false);
    }
  };

  const handleImportScan = async (scanId: string, assetIds?: string[]) => {
    if (!activeCanvas) return;
    try {
      await importScanToCanvas(activeCanvas.id, scanId, assetIds ? { asset_ids: assetIds } : undefined);
      await loadCanvas(activeCanvas.id);
      setShowImportModal(false);
    } catch {
      // silently fail
    }
  };

  const handleExport = async (format: string) => {
    if (!activeCanvas) return;
    try {
      const data = await exportCanvas(activeCanvas.id, format);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${activeCanvas.name.replace(/\s+/g, "_")}_canvas.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // silently fail
    }
  };

  const onConnect: OnConnect = useCallback(
    async (connection: Connection) => {
      if (!activeCanvas || !connection.source || !connection.target) return;
      try {
        const edge = await addCanvasEdge(activeCanvas.id, {
          source_node_id: connection.source,
          target_node_id: connection.target,
          label: "",
          edge_type: "default",
        });
        setEdges((eds) => addEdge({ ...connection, id: edge.id, style: { stroke: "#3B82F6", strokeWidth: 1.5 } }, eds));
      } catch {
        // silently fail
      }
    },
    [activeCanvas, setEdges]
  );

  const onNodeClick = useCallback((_: any, node: Node) => {
    setSelectedNode(node);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  const filteredNodes = useMemo(() => {
    return nodes.filter((n) => {
      if (filterType && n.data.asset_type !== filterType) return false;
      if (filterRisk && n.data.risk_level !== filterRisk) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        return (n.data.label as string).toLowerCase().includes(q);
      }
      return true;
    });
  }, [nodes, filterType, filterRisk, searchQuery]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Canvas List Sidebar */}
      <div className={cn(
        "w-64 border-r border-border/50 bg-card/50 flex flex-col shrink-0 transition-all duration-300",
        showSidebar ? "translate-x-0" : "-translate-x-full md:translate-x-0",
        "fixed md:relative z-30 h-full"
      )}>
        <div className="p-3 border-b border-border/30">
          <button
            onClick={handleCreateCanvas}
            className="flex items-center gap-2 w-full rounded-lg bg-primary/10 px-3 py-2.5 text-sm font-medium text-primary hover:bg-primary/20 transition-colors"
          >
            <Plus className="h-4 w-4" />
            New Canvas
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {canvases.map((c) => (
            <div
              key={c.id}
              className={cn(
                "group flex items-center gap-2 rounded-lg px-3 py-2 text-sm cursor-pointer transition-colors",
                activeCanvas?.id === c.id
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-muted/30"
              )}
              onClick={() => loadCanvas(c.id)}
            >
              <span className="flex-1 truncate">{c.name}</span>
              <span className="text-[10px] text-muted-foreground">{c.node_count}</span>
              <button
                onClick={(e) => { e.stopPropagation(); handleDeleteCanvas(c.id); }}
                className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Main Canvas */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Toolbar */}
        <div className="flex items-center gap-2 border-b border-border/50 bg-card/30 backdrop-blur-xl px-4 py-2">
          <button onClick={() => setShowSidebar(!showSidebar)} className="p-1.5 rounded-lg hover:bg-muted/30 md:hidden">
            <Settings className="h-4 w-4" />
          </button>
          <h2 className="text-sm font-semibold truncate">{activeCanvas?.name || "No Canvas"}</h2>
          <div className="flex-1" />
          <div className="flex items-center gap-1.5">
            <div className="relative">
              <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search nodes..."
                className="h-7 w-40 rounded-lg border border-border/50 bg-muted/30 pl-7 pr-2 text-xs outline-none focus:border-primary/50"
              />
            </div>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="h-7 rounded-lg border border-border/50 bg-muted/30 px-2 text-xs"
            >
              <option value="">All types</option>
              {Object.entries(ASSET_TYPE_CONFIG).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </select>
            <select
              value={filterRisk}
              onChange={(e) => setFilterRisk(e.target.value)}
              className="h-7 rounded-lg border border-border/50 bg-muted/30 px-2 text-xs"
            >
              <option value="">All risks</option>
              {Object.keys(RISK_COLORS).map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>
            <button
              onClick={() => setShowImportModal(true)}
              className="flex items-center gap-1 h-7 rounded-lg border border-border/50 bg-muted/30 px-2 text-xs hover:bg-muted/50"
            >
              <Upload className="h-3 w-3" /> Import
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !activeCanvas}
              className="flex items-center gap-1 h-7 rounded-lg bg-primary/10 px-2 text-xs text-primary hover:bg-primary/20"
            >
              {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />} Save
            </button>
            <button
              onClick={() => handleExport("json")}
              disabled={!activeCanvas}
              className="flex items-center gap-1 h-7 rounded-lg border border-border/50 bg-muted/30 px-2 text-xs hover:bg-muted/50"
            >
              <Download className="h-3 w-3" /> Export
            </button>
          </div>
        </div>

        {/* React Flow Canvas */}
        <div ref={reactFlowWrapper} className="flex-1">
          {activeCanvas ? (
            <ReactFlow
              nodes={filteredNodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={onNodeClick}
              onPaneClick={onPaneClick}
              nodeTypes={nodeTypes}
              fitView
              snapToGrid
              snapGrid={[15, 15]}
              defaultEdgeOptions={{ type: "default", animated: false }}
              proOptions={{ hideAttribution: true }}
            >
              <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#374151" />
              <Controls className="!bg-card !border-border/50 !shadow-lg" />
              <MiniMap
                nodeColor={(n) => {
                  const config = ASSET_TYPE_CONFIG[n.data?.asset_type as string];
                  return config?.color || "#6B7280";
                }}
                maskColor="rgba(0,0,0,0.5)"
                className="!bg-card/80 !border-border/50"
              />
            </ReactFlow>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="relative mb-6">
                <div className="absolute inset-0 rounded-full bg-primary/20 blur-2xl" />
                <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl border border-border/50 bg-card/80">
                  <Network className="h-8 w-8 text-primary" />
                </div>
              </div>
              <h2 className="text-xl font-bold mb-2">Intelligence Canvas</h2>
              <p className="text-sm text-muted-foreground max-w-md mb-6">
                Create a visual relationship map of your attack surface. Import scan data or add custom nodes.
              </p>
              <button
                onClick={handleCreateCanvas}
                className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
              >
                <Plus className="h-4 w-4" />
                Create Canvas
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Import Modal */}
      <AnimatePresence>
        {showImportModal && (
          <ImportModal
            onImport={handleImportScan}
            onClose={() => setShowImportModal(false)}
          />
        )}
      </AnimatePresence>

      {/* Node Properties Panel */}
      <AnimatePresence>
        {selectedNode && (
          <NodePropertiesPanel
            node={selectedNode}
            canvasId={activeCanvas?.id || ""}
            onClose={() => setSelectedNode(null)}
            onUpdate={async (data) => {
              setNodes((nds) => nds.map((n) => n.id === selectedNode.id ? { ...n, data: { ...n.data, ...data } } : n));
              if (selectedNode.data.canvas_node_id) {
                await updateCanvasNode(activeCanvas!.id, selectedNode.data.canvas_node_id as string, data);
              }
            }}
            onDelete={async () => {
              if (selectedNode.data.canvas_node_id) {
                await deleteCanvasNode(activeCanvas!.id, selectedNode.data.canvas_node_id as string);
              }
              setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id));
              setEdges((eds) => eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id));
              setSelectedNode(null);
            }}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

function ImportModal({ onImport, onClose }: { onImport: (scanId: string, assetIds?: string[]) => void; onClose: () => void }) {
  const [step, setStep] = useState<"select" | "preview">("select");
  const [scans, setScans] = useState<Scan[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedScan, setSelectedScan] = useState<Scan | null>(null);
  const [preview, setPreview] = useState<any>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("subdomains");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    listImportableScans(50).then((data) => {
      setScans(data);
      setLoading(false);
    });
  }, []);

  const handleSelectScan = async (scan: Scan) => {
    setSelectedScan(scan);
    setPreviewLoading(true);
    setStep("preview");
    try {
      const data = await previewScanAssets(scan.id);
      setPreview(data);
      const firstTab = Object.keys(data.counts).find((k) => data.counts[k] > 0) || "subdomains";
      setActiveTab(firstTab);
    } catch {
      setPreview(null);
    } finally {
      setPreviewLoading(false);
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (!preview) return;
    const items = preview.assets[activeTab] || [];
    const allSelected = items.every((a: any) => selectedIds.has(a.asset_id));
    if (allSelected) {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        items.forEach((a: any) => next.delete(a.asset_id));
        return next;
      });
    } else {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        items.forEach((a: any) => next.add(a.asset_id));
        return next;
      });
    }
  };

  const handleImport = () => {
    if (!selectedScan) return;
    if (selectedIds.size === 0) {
      onImport(selectedScan.id);
    } else {
      onImport(selectedScan.id, Array.from(selectedIds));
    }
  };

  const tabs = preview
    ? Object.entries(preview.counts)
        .filter(([_, count]) => (count as number) > 0)
        .map(([key, count]) => ({ key, count: count as number }))
    : [];

  const filteredItems = preview && preview.assets[activeTab]
    ? preview.assets[activeTab].filter((a: any) =>
        searchQuery ? a.label.toLowerCase().includes(searchQuery.toLowerCase()) : true
      )
    : [];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.95 }}
        animate={{ scale: 1 }}
        exit={{ scale: 0.95 }}
        className="w-full max-w-5xl max-h-[85vh] rounded-xl border border-border/50 bg-card shadow-2xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border/30 px-6 py-4 shrink-0">
          <div className="flex items-center gap-3">
            {step === "preview" && (
              <button onClick={() => { setStep("select"); setSelectedScan(null); setPreview(null); setSelectedIds(new Set()); }}
                className="text-muted-foreground hover:text-foreground">
                &larr;
              </button>
            )}
            <div>
              <h3 className="text-sm font-semibold">
                {step === "select" ? "Select Scan to Import" : `Import from ${selectedScan?.domain}`}
              </h3>
              {step === "preview" && (
                <p className="text-[10px] text-muted-foreground mt-0.5">{preview?.counts ? String(Object.values(preview.counts as Record<string, number>).reduce((a, b) => a + b, 0)) : "0"} total assets</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {step === "preview" && (
              <button onClick={handleImport}
                className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90">
                <Upload className="h-3 w-3" />
                Import {selectedIds.size > 0 ? `Selected (${selectedIds.size})` : "All"}
              </button>
            )}
            <button onClick={onClose} className="p-1 rounded hover:bg-muted/30"><X className="h-4 w-4" /></button>
          </div>
        </div>

        {/* Step 1: Scan Selection */}
        {step === "select" && (
          <div className="flex-1 overflow-y-auto p-6">
            {loading ? (
              <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
            ) : scans.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-12">No completed scans available. Run a scan first.</p>
            ) : (
              <div className="space-y-2">
                {scans.map((scan) => (
                  <button key={scan.id} onClick={() => handleSelectScan(scan)}
                    className="flex items-center gap-3 w-full rounded-lg border border-border/30 px-4 py-3 text-left hover:bg-muted/30 transition-colors">
                    <Globe className="h-4 w-4 text-primary shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium">{scan.domain}</p>
                      <p className="text-[10px] text-muted-foreground">{scan.scan_type} &middot; {new Date(scan.created_at).toLocaleDateString()}</p>
                    </div>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Step 2: Asset Table */}
        {step === "preview" && (
          <div className="flex flex-col flex-1 min-h-0">
            {previewLoading ? (
              <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
            ) : !preview ? (
              <p className="text-sm text-muted-foreground text-center py-12">Failed to load scan data.</p>
            ) : (
              <>
                {/* Tabs */}
                <div className="flex items-center gap-1 border-b border-border/30 px-4 overflow-x-auto shrink-0">
                  {tabs.map(({ key, count }) => (
                    <button key={key} onClick={() => { setActiveTab(key); setSearchQuery(""); }}
                      className={cn(
                        "flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium border-b-2 transition-colors whitespace-nowrap",
                        activeTab === key ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
                      )}>
                      <span className="capitalize">{key.replace(/_/g, " ")}</span>
                      <span className={cn(
                        "rounded-full px-1.5 py-0.5 text-[10px]",
                        activeTab === key ? "bg-primary/10" : "bg-muted/50"
                      )}>{count}</span>
                    </button>
                  ))}
                </div>

                {/* Search + Bulk Actions */}
                <div className="flex items-center gap-2 px-4 py-2 border-b border-border/20 shrink-0">
                  <div className="relative flex-1 max-w-xs">
                    <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
                    <input value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder={`Search ${activeTab.replace(/_/g, " ")}...`}
                      className="h-7 w-full rounded-lg border border-border/50 bg-muted/30 pl-7 pr-2 text-xs outline-none focus:border-primary/50" />
                  </div>
                  <button onClick={toggleAll}
                    className="flex items-center gap-1 h-7 rounded-lg border border-border/50 bg-muted/30 px-2 text-[10px] hover:bg-muted/50">
                    {filteredItems.length > 0 && filteredItems.every((a: any) => selectedIds.has(a.asset_id)) ? "Deselect All" : "Select All"}
                  </button>
                  {selectedIds.size > 0 && (
                    <span className="text-[10px] text-primary">{selectedIds.size} selected</span>
                  )}
                </div>

                {/* Table */}
                <div className="flex-1 overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0 bg-card/95 backdrop-blur-sm">
                      <tr className="text-left text-muted-foreground border-b border-border/30">
                        <th className="w-8 px-4 py-2">
                          <input type="checkbox" checked={filteredItems.length > 0 && filteredItems.every((a: any) => selectedIds.has(a.asset_id))}
                            onChange={toggleAll} className="rounded" />
                        </th>
                        <th className="px-2 py-2">Name</th>
                        <th className="px-2 py-2">Risk</th>
                        {activeTab === "subdomains" && <th className="px-2 py-2">Alive</th>}
                        {activeTab === "subdomains" && <th className="px-2 py-2">IPs</th>}
                        {activeTab === "ports" && <th className="px-2 py-2">Port</th>}
                        {activeTab === "ports" && <th className="px-2 py-2">Service</th>}
                        {activeTab === "ports" && <th className="px-2 py-2">Version</th>}
                        {activeTab === "ssl_certificates" && <th className="px-2 py-2">Grade</th>}
                        {activeTab === "ssl_certificates" && <th className="px-2 py-2">Issuer</th>}
                        {activeTab === "dns_records" && <th className="px-2 py-2">Type</th>}
                        {activeTab === "dns_records" && <th className="px-2 py-2">Value</th>}
                        {activeTab === "technologies" && <th className="px-2 py-2">Category</th>}
                        {activeTab === "technologies" && <th className="px-2 py-2">Version</th>}
                        {activeTab === "vulnerabilities" && <th className="px-2 py-2">Severity</th>}
                        {activeTab === "vulnerabilities" && <th className="px-2 py-2">Host</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {filteredItems.map((asset: any) => {
                        const riskColor = RISK_COLORS[asset.risk_level] || "#6B7280";
                        return (
                          <tr key={asset.asset_id}
                            className={cn("border-b border-border/20 hover:bg-muted/20 cursor-pointer transition-colors",
                              selectedIds.has(asset.asset_id) && "bg-primary/5"
                            )}
                            onClick={() => toggleSelect(asset.asset_id)}>
                            <td className="px-4 py-2">
                              <input type="checkbox" checked={selectedIds.has(asset.asset_id)}
                                onChange={() => toggleSelect(asset.asset_id)}
                                onClick={(e) => e.stopPropagation()}
                                className="rounded" />
                            </td>
                            <td className="px-2 py-2 font-medium max-w-xs truncate">{asset.label}</td>
                            <td className="px-2 py-2">
                              <span className="inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium"
                                style={{ backgroundColor: riskColor + "15", color: riskColor }}>
                                <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: riskColor }} />
                                {asset.risk_level}
                              </span>
                            </td>
                            {activeTab === "subdomains" && (
                              <td className="px-2 py-2">
                                {asset.is_alive === true ? <span className="text-green-400">Yes</span> :
                                 asset.is_alive === false ? <span className="text-red-400">No</span> :
                                 <span className="text-muted-foreground">-</span>}
                              </td>
                            )}
                            {activeTab === "subdomains" && (
                              <td className="px-2 py-2 text-muted-foreground truncate max-w-[150px]">
                                {(asset.detail.ip_addresses || []).join(", ") || "-"}
                              </td>
                            )}
                            {activeTab === "ports" && <td className="px-2 py-2">{asset.detail.port}</td>}
                            {activeTab === "ports" && <td className="px-2 py-2">{asset.detail.service}</td>}
                            {activeTab === "ports" && <td className="px-2 py-2 text-muted-foreground">{asset.detail.version || "-"}</td>}
                            {activeTab === "ssl_certificates" && (
                              <td className="px-2 py-2">
                                <span className={cn("font-mono font-bold",
                                  ["A", "A+"].includes(asset.detail.grade) ? "text-green-400" :
                                  asset.detail.grade === "B" ? "text-yellow-400" :
                                  "text-red-400"
                                )}>{asset.detail.grade || "N/A"}</span>
                              </td>
                            )}
                            {activeTab === "ssl_certificates" && (
                              <td className="px-2 py-2 text-muted-foreground truncate max-w-[200px]">{asset.detail.issuer || "-"}</td>
                            )}
                            {activeTab === "dns_records" && <td className="px-2 py-2">{asset.detail.type}</td>}
                            {activeTab === "dns_records" && (
                              <td className="px-2 py-2 text-muted-foreground truncate max-w-[200px]">{asset.detail.value}</td>
                            )}
                            {activeTab === "technologies" && <td className="px-2 py-2">{asset.detail.category || "-"}</td>}
                            {activeTab === "technologies" && <td className="px-2 py-2 text-muted-foreground">{asset.detail.version || "-"}</td>}
                            {activeTab === "vulnerabilities" && (
                              <td className="px-2 py-2">
                                <span className="capitalize">{asset.detail.severity}</span>
                              </td>
                            )}
                            {activeTab === "vulnerabilities" && (
                              <td className="px-2 py-2 text-muted-foreground">{asset.detail.host || "-"}</td>
                            )}
                          </tr>
                        );
                      })}
                      {filteredItems.length === 0 && (
                        <tr><td colSpan={20} className="px-4 py-8 text-center text-muted-foreground">No assets match your search.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}
      </motion.div>
    </motion.div>
  );
}

function NodePropertiesPanel({
  node, canvasId, onClose, onUpdate, onDelete,
}: {
  node: Node; canvasId: string; onClose: () => void;
  onUpdate: (data: any) => void; onDelete: () => void;
}) {
  const [label, setLabel] = useState(node.data.label as string);
  const [notes, setNotes] = useState((node.data.notes as string) || "");
  const [risk, setRisk] = useState((node.data.risk_level as string) || "informational");
  const [tagInput, setTagInput] = useState("");
  const tags = (node.data.tags as string[]) || [];

  const handleSave = () => {
    onUpdate({ label, notes, risk_level: risk });
  };

  const addTag = () => {
    if (tagInput.trim() && !tags.includes(tagInput.trim())) {
      onUpdate({ tags: [...tags, tagInput.trim()] });
      setTagInput("");
    }
  };

  const removeTag = (tag: string) => {
    onUpdate({ tags: tags.filter((t) => t !== tag) });
  };

  return (
    <motion.div
      initial={{ x: 300, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 300, opacity: 0 }}
      className="w-72 border-l border-border/50 bg-card/80 backdrop-blur-xl flex flex-col shrink-0"
    >
      <div className="flex items-center justify-between border-b border-border/30 px-4 py-3">
        <h3 className="text-sm font-semibold">Properties</h3>
        <button onClick={onClose} className="p-1 rounded hover:bg-muted/30"><X className="h-4 w-4" /></button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div className="space-y-2">
          <label className="text-xs font-medium">Label</label>
          <input value={label} onChange={(e) => setLabel(e.target.value)} onBlur={handleSave}
            className="w-full rounded-lg border border-border/50 bg-muted/30 px-3 py-2 text-sm outline-none" />
        </div>
        <div className="space-y-2">
          <label className="text-xs font-medium">Risk Level</label>
          <select value={risk} onChange={(e) => { setRisk(e.target.value); onUpdate({ risk_level: e.target.value }); }}
            className="w-full rounded-lg border border-border/50 bg-muted/30 px-3 py-2 text-sm">
            {Object.keys(RISK_COLORS).map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
        </div>
        <div className="space-y-2">
          <label className="text-xs font-medium">Notes</label>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} onBlur={handleSave}
            className="w-full rounded-lg border border-border/50 bg-muted/30 px-3 py-2 text-sm outline-none min-h-[80px]" />
        </div>
        <div className="space-y-2">
          <label className="text-xs font-medium">Tags</label>
          <div className="flex gap-1.5">
            <input value={tagInput} onChange={(e) => setTagInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addTag()}
              className="flex-1 rounded-lg border border-border/50 bg-muted/30 px-3 py-1.5 text-xs outline-none" placeholder="Add tag..." />
            <button onClick={addTag} className="rounded-lg bg-primary/10 px-2 text-xs text-primary hover:bg-primary/20">Add</button>
          </div>
          <div className="flex flex-wrap gap-1">
            {tags.map((tag) => (
              <span key={tag} className="flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] text-primary">
                {tag}
                <button onClick={() => removeTag(tag)} className="hover:text-destructive"><X className="h-2.5 w-2.5" /></button>
              </span>
            ))}
          </div>
        </div>
        <button onClick={onDelete} className="flex items-center gap-2 w-full rounded-lg border border-destructive/30 px-3 py-2 text-xs text-destructive hover:bg-destructive/10">
          <Trash2 className="h-3 w-3" /> Delete Node
        </button>
      </div>
    </motion.div>
  );
}

export default function IntelligenceCanvasPage() {
  return (
    <ProtectedRoute>
      <ReactFlowProvider>
        <CanvasContent />
      </ReactFlowProvider>
    </ProtectedRoute>
  );
}
