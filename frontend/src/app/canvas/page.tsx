"use client";

import { useCallback, useState, useEffect, useRef, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  addEdge,
  BackgroundVariant,
  type Connection,
  type Edge,
  type Node,
  type NodeTypes,
  type OnConnect,
  Panel,
  Handle,
  Position,
  ReactFlowProvider,
  useReactFlow,
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
  X,
  ChevronRight,
  Globe,
  Server,
  Lock as LockIcon,
  Network,
  Cpu,
  Bug,
  FileText,
  Settings,
  Circle,
  Hexagon,
  Triangle,
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

// ---------------------------------------------------------------------------
// Node palette categories
// ---------------------------------------------------------------------------

const NODE_CATEGORIES = [
  {
    label: "Data",
    nodes: [
      { type: "domain", icon: Globe, color: "#EC3C53", label: "Domain", inputs: ["Flow"], outputs: ["Flow", "Data"] },
      { type: "subdomain", icon: Server, color: "#06B6D4", label: "Subdomain", inputs: ["Flow"], outputs: ["Flow", "Data"] },
      { type: "ip_address", icon: Circle, color: "#818CF8", label: "IP Address", inputs: ["Flow"], outputs: ["Flow", "Data"] },
    ],
  },
  {
    label: "Analysis",
    nodes: [
      { type: "port", icon: Server, color: "#EC4899", label: "Port Scan", inputs: ["Flow", "Target"], outputs: ["Flow", "Ports"] },
      { type: "ssl_certificate", icon: LockIcon, color: "#EC3C53", label: "SSL Check", inputs: ["Flow", "Target"], outputs: ["Flow", "Cert"] },
      { type: "dns_record", icon: Network, color: "#F8B925", label: "DNS Lookup", inputs: ["Flow", "Target"], outputs: ["Flow", "Records"] },
      { type: "technology", icon: Cpu, color: "#818CF8", label: "Tech Detect", inputs: ["Flow", "Target"], outputs: ["Flow", "Tech"] },
    ],
  },
  {
    label: "Security",
    nodes: [
      { type: "vulnerability", icon: Bug, color: "#F05151", label: "Vuln Scan", inputs: ["Flow", "Target"], outputs: ["Flow", "Findings"] },
      { type: "scan_network", icon: Network, color: "#EC3C53", label: "Scan Network", inputs: ["Flow"], outputs: ["Flow", "Devices"] },
    ],
  },
  {
    label: "Output",
    nodes: [
      { type: "print", icon: FileText, color: "#06B6D4", label: "Print", inputs: ["Flow", "Message"], outputs: ["Flow"] },
      { type: "note", icon: FileText, color: "#6B7280", label: "Note", inputs: [], outputs: [] },
    ],
  },
];

// ---------------------------------------------------------------------------
// Port-based node — like the node editor in Image 1
// ---------------------------------------------------------------------------

const NODE_COLORS: Record<string, string> = {
  domain: "#EC3C53", subdomain: "#06B6D4", ip_address: "#818CF8",
  port: "#EC4899", ssl_certificate: "#EC3C53", dns_record: "#F8B925",
  technology: "#818CF8", vulnerability: "#F05151", organization: "#6366F1",
  email: "#EC4899", cloud_asset: "#06B6D4", web_application: "#EC3C53",
  external_service: "#F67A31", note: "#6B7280", print: "#06B6D4",
  scan_network: "#EC3C53",
};

function PortNode({ data, selected }: { data: any; selected?: boolean }) {
  const color = NODE_COLORS[data.asset_type || data.nodeType] || "#EC3C53";
  const inputs: string[] = data.inputs || [];
  const outputs: string[] = data.outputs || [];

  return (
    <div
      className={cn("relative transition-all duration-150", selected && "scale-105")}
      style={{ minWidth: 160 }}
    >
      {/* Input handles (left side) */}
      {inputs.map((label, i) => (
        <Handle
          key={`in-${i}`}
          type="target"
          position={Position.Left}
          id={`in-${i}`}
          style={{
            width: 8, height: 8, borderRadius: "50%",
            background: color, border: `2px solid #141414`,
            top: 30 + i * 18,
          }}
        />
      ))}

      {/* Output handles (right side) */}
      {outputs.map((label, i) => (
        <Handle
          key={`out-${i}`}
          type="source"
          position={Position.Right}
          id={`out-${i}`}
          style={{
            width: 8, height: 8, borderRadius: "50%",
            background: color, border: `2px solid #141414`,
            top: 30 + i * 18,
          }}
        />
      ))}

      {/* Node body */}
      <div
        className="rounded-lg overflow-hidden"
        style={{
          background: "#1B1B1B",
          border: `1.5px solid ${selected ? color : color + "44"}`,
          boxShadow: selected ? `0 0 16px ${color}44` : `0 0 8px ${color}11`,
        }}
      >
        {/* Header */}
        <div
          className="flex items-center gap-2 px-3 py-2"
          style={{ background: `${color}11`, borderBottom: `1px solid ${color}22` }}
        >
          <span className=" text-[11px] font-semibold uppercase" style={{ color }}>
            {data.label || data.asset_type || "Node"}
          </span>
        </div>

        {/* Ports */}
        <div className="px-3 py-2 space-y-1">
          {inputs.map((label, i) => (
            <div key={`in-${i}`} className="flex items-center gap-2 text-[9px] font-mono" style={{ color: `${color}88` }}>
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
              {label}
            </div>
          ))}
          {outputs.map((label, i) => (
            <div key={`out-${i}`} className="flex items-center justify-end gap-2 text-[9px] font-mono" style={{ color: `${color}88` }}>
              {label}
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
            </div>
          ))}
        </div>

        {/* Description */}
        {data.notes && (
          <div className="px-3 pb-2">
            <p className="text-[9px] text-muted-foreground line-clamp-2">{data.notes}</p>
          </div>
        )}
      </div>
    </div>
  );
}

const nodeTypes: NodeTypes = { asset: PortNode as any };

// ---------------------------------------------------------------------------
// Main canvas content
// ---------------------------------------------------------------------------

function CanvasContent() {
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const { fitView } = useReactFlow();

  const [canvases, setCanvases] = useState<CanvasType[]>([]);
  const [activeCanvas, setActiveCanvas] = useState<CanvasDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [showImportModal, setShowImportModal] = useState(false);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  // Palette search
  const [paletteSearch, setPaletteSearch] = useState("");

  const filteredCategories = useMemo(() => {
    if (!paletteSearch.trim()) return NODE_CATEGORIES;
    const q = paletteSearch.toLowerCase();
    return NODE_CATEGORIES.map((cat) => ({
      ...cat,
      nodes: cat.nodes.filter((n) => n.label.toLowerCase().includes(q) || n.type.includes(q)),
    })).filter((cat) => cat.nodes.length > 0);
  }, [paletteSearch]);

  useEffect(() => { loadCanvases(); }, []);

  useEffect(() => {
    if (activeCanvas) {
      const rfNodes: Node[] = activeCanvas.nodes
        .filter((n) => !n.hidden)
        .map((n) => {
          const cat = NODE_CATEGORIES.flatMap((c) => c.nodes).find((c) => c.type === n.asset_type);
          return {
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
              nodeType: n.asset_type,
              inputs: cat?.inputs || ["Flow"],
              outputs: cat?.outputs || ["Flow"],
            },
            style: { width: 180 },
          };
        });
      const rfEdges: Edge[] = activeCanvas.edges.map((e) => ({
        id: e.id,
        source: e.source_node_id,
        target: e.target_node_id,
        label: e.label,
        type: "smoothstep",
        animated: e.animated,
        style: { stroke: "#EC3C5366", strokeWidth: 1.5 },
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
      if (data.length > 0) await loadCanvas(data[0].id);
    } catch {} finally { setLoading(false); }
  };

  const loadCanvas = async (id: string) => {
    try { setActiveCanvas(await getCanvas(id)); } catch {}
  };

  const handleCreateCanvas = async () => {
    try {
      const canvas = await createCanvas({ name: `Canvas ${canvases.length + 1}` });
      setCanvases((prev) => [canvas, ...prev]);
      await loadCanvas(canvas.id);
    } catch {}
  };

  const handleDeleteCanvas = async (id: string) => {
    try {
      await deleteCanvas(id);
      setCanvases((prev) => prev.filter((c) => c.id !== id));
      if (activeCanvas?.id === id) { setActiveCanvas(null); setNodes([]); setEdges([]); }
    } catch {}
  };

  const handleSave = async () => {
    if (!activeCanvas) return;
    setSaving(true);
    try {
      for (const n of nodes) {
        if (n.data.canvas_node_id) {
          await updateCanvasNode(activeCanvas.id, n.data.canvas_node_id as string, { x: n.position.x, y: n.position.y });
        }
      }
    } catch {} finally { setSaving(false); }
  };

  const handleImportScan = async (scanId: string, assetIds?: string[]) => {
    if (!activeCanvas) return;
    try {
      await importScanToCanvas(activeCanvas.id, scanId, assetIds ? { asset_ids: assetIds } : undefined);
      await loadCanvas(activeCanvas.id);
      setShowImportModal(false);
    } catch {}
  };

  const handleExport = async () => {
    if (!activeCanvas) return;
    try {
      const data = await exportCanvas(activeCanvas.id, "json");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `${activeCanvas.name.replace(/\s+/g, "_")}_canvas.json`; a.click();
      URL.revokeObjectURL(url);
    } catch {}
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
        setEdges((eds) => addEdge({ ...connection, id: edge.id, style: { stroke: "#EC3C5366", strokeWidth: 1.5 }, type: "smoothstep" }, eds));
      } catch {}
    },
    [activeCanvas, setEdges]
  );

  const onNodeClick = useCallback((_: any, node: Node) => setSelectedNode(node), []);
  const onPaneClick = useCallback(() => setSelectedNode(null), []);

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    async (event: React.DragEvent) => {
      event.preventDefault();
      const typeStr = event.dataTransfer.getData("application/canvas-node-type");
      if (!typeStr || !activeCanvas) return;

      const cat = NODE_CATEGORIES.flatMap((c) => c.nodes).find((c) => c.type === typeStr);
      if (!cat) return;

      const bounds = reactFlowWrapper.current?.getBoundingClientRect();
      if (!bounds) return;

      const position = {
        x: event.clientX - bounds.left - 80,
        y: event.clientY - bounds.top - 20,
      };

      try {
        const newNode = await importScanToCanvas(activeCanvas.id, "manual", {
          asset_ids: [], asset_type: typeStr, label: cat.label, x: position.x, y: position.y,
        } as any);
        await loadCanvas(activeCanvas.id);
      } catch {
        // Fallback: add locally
        const localId = `local-${Date.now()}`;
        setNodes((nds) => nds.concat({
          id: localId, type: "asset", position,
          data: { label: cat.label, asset_type: typeStr, nodeType: typeStr, inputs: cat.inputs, outputs: cat.outputs, notes: "" },
          style: { width: 180 },
        }));
      }
    },
    [activeCanvas, setNodes]
  );

  // Generate pseudo-code from nodes/edges
  const generatedCode = useMemo(() => {
    if (nodes.length === 0) return "# No nodes on canvas\n";
    const lines: string[] = ["# Script Start"];
    for (const n of nodes) {
      const d = n.data as any;
      const type = d.asset_type || d.nodeType;
      if (type === "scan_network") {
        lines.push(`devices = gn.scan_network()`);
      } else if (type === "print") {
        lines.push(`print(devices)`);
      } else if (type === "domain" || type === "subdomain") {
        lines.push(`${d.label || "target"} = gn.resolve("${d.label || "example.com"}")`);
      } else if (type === "vulnerability") {
        lines.push(`vulns = gn.scan_vulns(${d.label || "target"})`);
      } else {
        lines.push(`${d.label || type} = gn.${type}()`);
      }
    }
    return lines.join("\n");
  }, [nodes]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen" style={{ background: "#0B0B0B" }}>
        <Loader2 className="h-6 w-6 animate-spin" style={{ color: "#EC3C53" }} />
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "#0B0B0B" }}>
      {/* ── Left sidebar: Node palette ── */}
      <div className="w-56 border-r flex flex-col shrink-0" style={{ borderColor: "#292929", background: "#141414" }}>
        {/* Header */}
        <div className="px-3 py-2 border-b flex items-center justify-between" style={{ borderColor: "#292929" }}>
          <span className=" text-[11px] font-semibold uppercase tracking-wider" style={{ color: "#EC3C53" }}>
            Node Editor
          </span>
          <span className="font-mono text-[9px] text-muted-foreground">*.gnt</span>
        </div>

        {/* Canvas list */}
        <div className="px-3 py-2 border-b" style={{ borderColor: "#292929" }}>
          <button
            onClick={handleCreateCanvas}
            className="flex items-center gap-1.5 w-full rounded px-2 py-1.5 text-[10px] font-mono transition-colors"
            style={{ background: "#EC3C5311", color: "#EC3C53", border: "1px solid #EC3C5333" }}
          >
            <Plus className="h-3 w-3" /> NEW
          </button>
          <div className="mt-1.5 space-y-0.5 max-h-24 overflow-y-auto">
            {canvases.map((c) => (
              <button
                key={c.id}
                onClick={() => loadCanvas(c.id)}
                className={cn(
                  "flex items-center justify-between w-full rounded px-2 py-1 text-[10px] font-mono transition-colors",
                  activeCanvas?.id === c.id ? "text-foreground" : "text-muted-foreground hover:text-foreground"
                )}
                style={{ background: activeCanvas?.id === c.id ? "#292929" : "transparent" }}
              >
                <span className="truncate">{c.name}</span>
                <button
                  onClick={(e) => { e.stopPropagation(); handleDeleteCanvas(c.id); }}
                  className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive"
                >
                  <Trash2 className="h-2.5 w-2.5" />
                </button>
              </button>
            ))}
          </div>
        </div>

        {/* Search */}
        <div className="px-3 py-2 border-b" style={{ borderColor: "#292929" }}>
          <div className="flex items-center gap-1.5 rounded px-2 py-1" style={{ background: "#1B1B1B", border: "1px solid #292929" }}>
            <Search className="h-3 w-3" style={{ color: "#EC3C5366" }} />
            <input
              value={paletteSearch}
              onChange={(e) => setPaletteSearch(e.target.value)}
              placeholder="Search nodes" aria-label="Search nodes"
              className="flex-1 bg-transparent text-[10px] font-mono focus:outline-none"
              style={{ color: "#EC3C53" }}
            />
          </div>
        </div>

        {/* Node categories */}
        <div className="flex-1 overflow-y-auto px-3 py-2 space-y-3">
          {filteredCategories.map((cat) => (
            <div key={cat.label}>
              <span className=" text-[11px] text-muted-foreground uppercase tracking-wider">
                {cat.label} ({cat.nodes.length})
              </span>
              <div className="mt-1 space-y-1">
                {cat.nodes.map((n) => (
                  <div
                    key={n.type}
                    draggable
                    onDragStart={(e) => {
                      e.dataTransfer.setData("application/canvas-node-type", n.type);
                      e.dataTransfer.effectAllowed = "move";
                    }}
                    className="flex items-center gap-2 rounded px-2 py-1.5 cursor-grab active:cursor-grabbing transition-colors hover:bg-white/5"
                  >
                    <span className="h-2 w-2 rounded-full" style={{ background: n.color }} />
                    <span className="font-mono text-[10px] text-foreground/80">{n.label}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Stats */}
        <div className="px-3 py-2 border-t font-mono text-[9px] text-muted-foreground" style={{ borderColor: "#292929" }}>
          Nodes: {nodes.length} | Connections: {edges.length}
        </div>
      </div>

      {/* ── Main area ── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Toolbar */}
        <div className="flex items-center gap-2 border-b px-4 py-1.5 shrink-0" style={{ borderColor: "#292929", background: "#141414ee" }}>
          <button onClick={handleCreateCanvas} className="flex items-center gap-1 rounded px-2 py-1 text-[10px] font-mono hover:bg-white/5" style={{ color: "#EC3C53" }}>
            <Plus className="h-3 w-3" /> NEW
          </button>
          <button onClick={() => activeCanvas && loadCanvas(activeCanvas.id)} className="flex items-center gap-1 rounded px-2 py-1 text-[10px] font-mono hover:bg-white/5 text-muted-foreground">
            OPEN
          </button>
          <button onClick={handleSave} disabled={saving || !activeCanvas} className="flex items-center gap-1 rounded px-2 py-1 text-[10px] font-mono hover:bg-white/5 text-muted-foreground">
            {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />} SAVE
          </button>
          <button onClick={() => { setNodes([]); setEdges([]); }} className="flex items-center gap-1 rounded px-2 py-1 text-[10px] font-mono hover:bg-white/5 text-muted-foreground">
            CLEAR
          </button>
          <div className="flex-1" />
          <button onClick={() => setShowImportModal(true)} className="flex items-center gap-1 rounded px-2 py-1 text-[10px] font-mono hover:bg-white/5 text-muted-foreground">
            <Upload className="h-3 w-3" /> IMPORT
          </button>
          <button onClick={handleExport} disabled={!activeCanvas} className="flex items-center gap-1 rounded px-2 py-1 text-[10px] font-mono hover:bg-white/5 text-muted-foreground">
            <Download className="h-3 w-3" /> EXPORT
          </button>
        </div>

        {/* Canvas */}
        <div ref={reactFlowWrapper} className="flex-1" onDragOver={onDragOver} onDrop={onDrop}>
          {activeCanvas ? (
            <ReactFlow
              nodes={nodes}
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
              defaultEdgeOptions={{ type: "smoothstep", animated: false }}
              proOptions={{ hideAttribution: true }}
              className="bg-transparent"
            >
              <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#29292944" />
              <Controls
                showZoom
                showFitView
                showInteractive={false}
                className="!rounded !border !bg-[#141414dd] !"
                style={{ borderColor: "#292929" }}
              />
            </ReactFlow>
          ) : (
            <div className="flex flex-col items-center justify-center h-full">
              <div className="text-center space-y-3">
                <Network className="h-10 w-10 mx-auto" style={{ color: "#292929" }} />
                <p className="font-mono text-xs text-muted-foreground">No canvas selected</p>
                <button
                  onClick={handleCreateCanvas}
                  className="font-mono text-[10px] px-3 py-1.5 rounded"
                  style={{ background: "#EC3C5311", color: "#EC3C53", border: "1px solid #EC3C5333" }}
                >
                  CREATE CANVAS
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Generated code panel (bottom) */}
        {activeCanvas && (
          <div className="shrink-0 border-t" style={{ borderColor: "#292929", background: "#141414" }}>
            <div className="flex items-center justify-between px-4 py-1.5 border-b" style={{ borderColor: "#292929" }}>
              <span className=" text-[11px] font-semibold uppercase tracking-wider" style={{ color: "#EC3C53" }}>
                Generated Code
              </span>
              <button
                onClick={() => navigator.clipboard.writeText(generatedCode)}
                className="font-mono text-[9px] text-muted-foreground hover:text-foreground"
              >
                copy
              </button>
            </div>
            <pre className="px-4 py-2 text-[10px] font-mono overflow-x-auto max-h-28" style={{ color: "#EC3C5388" }}>
              {generatedCode}
            </pre>
          </div>
        )}
      </div>

      {/* ── Node properties panel (right) ── */}
      <AnimatePresence>
        {selectedNode && (
          <motion.div
            initial={{ x: 240, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 240, opacity: 0 }}
            className="w-60 border-l flex flex-col shrink-0"
            style={{ borderColor: "#292929", background: "#141414" }}
          >
            <div className="flex items-center justify-between px-3 py-2 border-b" style={{ borderColor: "#292929" }}>
              <span className=" text-[11px] font-semibold uppercase" style={{ color: "#EC3C53" }}>
                Properties
              </span>
              <button onClick={() => setSelectedNode(null)} className="text-muted-foreground hover:text-foreground">
                <X className="h-3 w-3" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-3 space-y-3">
              <div>
                <label className=" text-[11px] text-muted-foreground uppercase">Label</label>
                <input
                  value={(selectedNode.data.label as string) || ""}
                  onChange={(e) => {
                    const val = e.target.value;
                    setNodes((nds) => nds.map((n) => n.id === selectedNode.id ? { ...n, data: { ...n.data, label: val } } : n));
                  }}
                  onBlur={async () => {
                    if (selectedNode.data.canvas_node_id && activeCanvas) {
                      await updateCanvasNode(activeCanvas.id, selectedNode.data.canvas_node_id as string, { label: selectedNode.data.label });
                    }
                  }}
                  className="w-full rounded px-2 py-1.5 text-[10px] font-mono mt-1 focus:outline-none"
                  style={{ background: "#1B1B1B", border: "1px solid #292929", color: "#EC3C53" }}
                />
              </div>
              <div>
                <label className=" text-[11px] text-muted-foreground uppercase">Type</label>
                <p className="font-mono text-[10px] mt-1" style={{ color: NODE_COLORS[selectedNode.data.asset_type as string] || "#EC3C53" }}>
                  {(selectedNode.data.asset_type as string) || "unknown"}
                </p>
              </div>
              <div>
                <label className=" text-[11px] text-muted-foreground uppercase">Notes</label>
                <textarea
                  value={(selectedNode.data.notes as string) || ""}
                  onChange={(e) => {
                    const val = e.target.value;
                    setNodes((nds) => nds.map((n) => n.id === selectedNode.id ? { ...n, data: { ...n.data, notes: val } } : n));
                  }}
                  className="w-full rounded px-2 py-1.5 text-[10px] font-mono mt-1 min-h-[60px] focus:outline-none"
                  style={{ background: "#1B1B1B", border: "1px solid #292929", color: "#EC3C5388" }}
                />
              </div>
              <button
                onClick={async () => {
                  if (selectedNode.data.canvas_node_id && activeCanvas) {
                    await deleteCanvasNode(activeCanvas.id, selectedNode.data.canvas_node_id as string);
                  }
                  setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id));
                  setEdges((eds) => eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id));
                  setSelectedNode(null);
                }}
                className="flex items-center gap-1.5 w-full rounded px-2 py-1.5 text-[10px] font-mono"
                style={{ color: "#F05151", border: "1px solid #F0515133" }}
              >
                <Trash2 className="h-3 w-3" /> DELETE
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Import modal ── */}
      <AnimatePresence>
        {showImportModal && (
          <ImportModal onImport={handleImportScan} onClose={() => setShowImportModal(false)} />
        )}
      </AnimatePresence>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Import modal (simplified)
// ---------------------------------------------------------------------------

function ImportModal({ onImport, onClose }: { onImport: (scanId: string, assetIds?: string[]) => void; onClose: () => void }) {
  const [scans, setScans] = useState<Scan[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedScan, setSelectedScan] = useState<Scan | null>(null);

  useEffect(() => { listImportableScans(50).then((d) => { setScans(d); setLoading(false); }); }, []);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "#0B0B0B88" }}
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.95 }}
        animate={{ scale: 1 }}
        exit={{ scale: 0.95 }}
        className="w-full max-w-md rounded-lg overflow-hidden"
        style={{ background: "#141414", border: "1px solid #292929" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: "#292929" }}>
          <span className=" text-[11px] font-semibold uppercase" style={{ color: "#EC3C53" }}>
            Import Scan
          </span>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="max-h-80 overflow-y-auto p-4 space-y-2">
          {loading ? (
            <div className="flex justify-center py-8"><Loader2 className="h-5 w-5 animate-spin" style={{ color: "#EC3C53" }} /></div>
          ) : scans.length === 0 ? (
            <p className="font-mono text-[10px] text-muted-foreground text-center py-8">No completed scans available.</p>
          ) : (
            scans.map((scan) => (
              <button
                key={scan.id}
                onClick={() => { onImport(scan.id); }}
                className="flex items-center gap-3 w-full rounded px-3 py-2.5 text-left transition-colors hover:bg-white/5"
                style={{ border: "1px solid #292929" }}
              >
                <Globe className="h-3.5 w-3.5 shrink-0" style={{ color: "#EC3C53" }} />
                <div className="flex-1 min-w-0">
                  <p className="font-mono text-[10px] text-foreground">{scan.domain}</p>
                  <p className="font-mono text-[9px] text-muted-foreground">{scan.scan_type}</p>
                </div>
                <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
              </button>
            ))
          )}
        </div>
      </motion.div>
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
