"use client";

import { memo, useEffect, useState, useCallback, useMemo, useRef } from "react";
import { listScans, getAssetGraph } from "@/lib/api";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  Waypoints,
  Globe,
  Bug,
  Loader2,
  Search,
  X,
  ChevronRight,
  ChevronDown,
  Maximize2,
  Minimize2,
  Flame,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useChecklistAutoComplete } from "@/components/onboarding/GettingStartedChecklist";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  Position,
  Handle,
  type Node,
  type Edge,
  type NodeProps,
  ReactFlowProvider,
  useReactFlow,
  useOnViewportChange,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  buildView,
  defaultExpandedGroups,
  groupHosts,
  groupKeyOfHost,
  indexGraph,
  DEFAULT_GROUP_LIMIT,
  DEFAULT_HOST_LIMIT,
  GROUP_BY_OPTIONS,
  GROUP_LIMIT_STEP,
  HOST_LIMIT_STEP,
  SEVERITIES,
  groupNodeId,
  type GraphIndex,
  type GroupBy,
  type GroupRecord,
  type HostRecord,
  type LayoutMode,
  type Severity,
  type SevCounts,
  type ViewResult,
} from "@/lib/attackGraphModel";
import type { Scan } from "@/types";

// ---------------------------------------------------------------------------
// Colours
// ---------------------------------------------------------------------------

const BRAND = "#EC3C53";
const CLEAN = "#71717A"; // host / group with no findings
const PORT = "#A1A1AA";

const SEVERITY_COLOR: Record<Severity, string> = {
  critical: "#F0518A",
  high: "#F67A31",
  medium: "#F8B925",
  low: "#3B82F6",
  info: "#818CF8",
};
const SEV_SHORT: Record<Severity, string> = { critical: "C", high: "H", medium: "M", low: "L", info: "I" };

const sevColor = (s?: Severity | null) => (s ? SEVERITY_COLOR[s] : CLEAN);

// ---------------------------------------------------------------------------
// Preferences (per viewer, best effort)
// ---------------------------------------------------------------------------

const PREF_KEY = "cazo_attack_graph_prefs";
function readPrefs(): { groupBy?: GroupBy; layout?: LayoutMode } {
  try {
    return JSON.parse(localStorage.getItem(PREF_KEY) || "{}");
  } catch {
    return {};
  }
}
function writePrefs(p: { groupBy: GroupBy; layout: LayoutMode }) {
  try {
    localStorage.setItem(PREF_KEY, JSON.stringify(p));
  } catch {
    /* storage unavailable */
  }
}

// ---------------------------------------------------------------------------
// Node components
// ---------------------------------------------------------------------------

/** Invisible handles at the node centre so edges meet nodes cleanly in both layouts. */
function CenterHandles({ layout }: { layout: LayoutMode }) {
  const style = layout === "radial" ? { opacity: 0, top: "50%", left: "50%", width: 1, height: 1, minWidth: 0, minHeight: 0, border: 0 } : { opacity: 0 };
  return (
    <>
      <Handle type="target" position={Position.Left} style={style} isConnectable={false} />
      <Handle type="source" position={Position.Right} style={style} isConnectable={false} />
    </>
  );
}

/**
 * Label that follows the ray from the root in radial mode (readable at any
 * density, never overlaps a sibling) and sits to the right in tree mode.
 */
function OrientedLabel({
  text,
  angle,
  layout,
  offset,
  color,
  className,
}: {
  text: string;
  angle: number;
  layout: LayoutMode;
  offset: number;
  color: string;
  className?: string;
}) {
  if (layout === "tree") {
    return (
      <span
        className={cn("absolute top-1/2 -translate-y-1/2 whitespace-nowrap font-mono text-[10px] pointer-events-none", className)}
        style={{ left: "calc(100% + 9px)", color }}
      >
        {text}
      </span>
    );
  }
  const deg = (angle * 180) / Math.PI;
  const flip = Math.cos(angle) < 0;
  return (
    <div
      className="absolute left-1/2 top-1/2 h-0 w-0 pointer-events-none"
      style={{ transform: `rotate(${flip ? deg + 180 : deg}deg)` }}
    >
      <span
        className={cn("absolute -translate-y-1/2 whitespace-nowrap font-mono text-[10px]", className)}
        style={flip ? { right: offset, color } : { left: offset, color }}
      >
        {text}
      </span>
    </div>
  );
}

function SevBar({ counts }: { counts: SevCounts }) {
  const items = SEVERITIES.filter((s) => counts[s] > 0 && s !== "info");
  if (!items.length) return null;
  return (
    <div className="flex items-center gap-1">
      {items.map((s) => (
        <span
          key={s}
          className="rounded px-1 font-mono text-[9px] font-semibold leading-[14px]"
          style={{ background: `${SEVERITY_COLOR[s]}22`, color: SEVERITY_COLOR[s] }}
        >
          {counts[s]}
          {SEV_SHORT[s]}
        </span>
      ))}
    </div>
  );
}

const RootNode = memo(function RootNode({ data }: NodeProps) {
  const d = data as any;
  return (
    <div className="relative flex h-[76px] w-[76px] items-center justify-center rounded-full"
      style={{
        background: `radial-gradient(circle at 30% 30%, ${BRAND}30, #141414 70%)`,
        border: `2px solid ${BRAND}`,
        boxShadow: `0 0 28px -4px ${BRAND}aa`,
      }}
    >
      <CenterHandles layout={d.layout} />
      <Globe className="h-7 w-7" style={{ color: BRAND }} />
      <div className="absolute top-[84px] left-1/2 -translate-x-1/2 whitespace-nowrap rounded px-2 py-0.5 text-center"
        style={{ background: "#141414ee", border: `1px solid ${BRAND}55` }}>
        <div className="font-mono text-[12px] font-semibold" style={{ color: BRAND }}>{d.label}</div>
        <div className="font-mono text-[9px] text-muted-foreground">{d.hostCount} hosts</div>
      </div>
    </div>
  );
});

function groupSize(n: number) {
  return Math.round(Math.min(84, 44 + Math.log2(Math.max(1, n)) * 5));
}

const GroupNode = memo(function GroupNode({ data, selected }: NodeProps) {
  const d = data as any;
  const color = sevColor(d.worst);
  const size = groupSize(d.hostCount);
  const risky = d.worst === "critical" || d.worst === "high";
  return (
    <div className="relative flex items-center justify-center cursor-pointer" style={{ width: size, height: size }}>
      <CenterHandles layout={d.layout} />
      {risky && (
        <span className="absolute rounded-full animate-pulse" style={{ inset: -7, border: `1px solid ${color}66`, boxShadow: `0 0 22px 2px ${color}44` }} />
      )}
      <div
        className="relative flex h-full w-full flex-col items-center justify-center rounded-full transition-shadow"
        style={{
          background: d.expanded ? `${color}26` : `radial-gradient(circle at 30% 30%, ${color}22, #141414 72%)`,
          border: `2px ${d.expanded ? "solid" : "dashed"} ${color}`,
          boxShadow: selected ? `0 0 26px 2px ${color}88` : `0 0 12px -2px ${color}66`,
        }}
      >
        <span className="font-mono text-[15px] font-bold leading-none text-foreground">{d.hostCount}</span>
        <span className="font-mono text-[8px] uppercase tracking-wider text-muted-foreground">hosts</span>
      </div>
      {d.findingCount > 0 && (
        <span
          className="absolute -top-1 -right-1 flex h-5 min-w-5 items-center justify-center gap-0.5 rounded-full px-1 font-mono text-[10px] font-bold text-white"
          style={{ background: color, boxShadow: `0 0 8px ${color}` }}
          title={`${d.findingCount} findings`}
        >
          <Bug className="h-2.5 w-2.5" />
          {d.findingCount}
        </span>
      )}
      <div
        className={cn(
          "absolute flex flex-col gap-0.5 rounded px-1.5 py-1 pointer-events-none",
          d.layout === "tree" ? "left-full ml-3 top-1/2 -translate-y-1/2 items-start" : "top-full mt-2 left-1/2 -translate-x-1/2 items-center"
        )}
        style={{ background: "#141414ee", border: `1px solid ${color}44` }}
      >
        <span className="flex items-center gap-1 whitespace-nowrap font-mono text-[11px] font-semibold" style={{ color: d.worst ? color : "#D4D4D8" }}>
          {d.expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          {d.label}
        </span>
        <SevBar counts={d.sevCounts} />
      </div>
    </div>
  );
});

const HostNode = memo(function HostNode({ data, selected }: NodeProps) {
  const d = data as any;
  const color = sevColor(d.worst);
  const risky = d.worst && d.worst !== "info";
  const size = risky ? 20 : 14;
  return (
    <div className="relative flex items-center justify-center cursor-pointer" style={{ width: size, height: size }}>
      <CenterHandles layout={d.layout} />
      <div
        className="h-full w-full rounded-full"
        style={{
          background: risky ? `${color}55` : "#1B1B1B",
          border: `2px solid ${color}`,
          boxShadow: selected ? `0 0 16px 3px ${color}` : risky ? `0 0 10px ${color}99` : "none",
        }}
      />
      {d.findingCount > 0 && (
        <span className="absolute -top-2 -right-2 rounded-full px-1 font-mono text-[8px] font-bold leading-[12px] text-white" style={{ background: color }}>
          {d.findingCount}
        </span>
      )}
      <OrientedLabel
        text={d.label}
        angle={d.angle}
        layout={d.layout}
        offset={size / 2 + 6}
        color={selected ? "#FFFFFF" : risky ? color : "#A1A1AA"}
        className={cn("ag-host-label", risky && "font-semibold", selected && "font-semibold")}
      />
    </div>
  );
});

const MoreNode = memo(function MoreNode({ data }: NodeProps) {
  const d = data as any;
  return (
    <div className="relative flex h-6 items-center cursor-pointer">
      <CenterHandles layout={d.layout} />
      <div className="whitespace-nowrap rounded-full border px-2.5 py-0.5 font-mono text-[10px] hover:brightness-125"
        style={{ borderColor: "#3F3F46", background: "#1B1B1BF0", color: "#D4D4D8", transform: d.layout === "radial" ? "translateX(-50%)" : undefined, marginLeft: d.layout === "radial" ? "50%" : 0 }}>
        {d.kind === "more-groups" ? `+${d.remaining} more groups · ${d.hosts} hosts` : `+${d.remaining} more · show ${d.step}`}
      </div>
    </div>
  );
});

const ChildNode = memo(function ChildNode({ data, selected }: NodeProps) {
  const d = data as any;
  const isVuln = d.type === "vulnerability";
  const color = isVuln ? sevColor(d.severity) : d.type === "certificate" ? "#F8B925" : PORT;
  const label = isVuln ? d.label : d.type === "port" ? `${d.label}${d.service ? " " + d.service : ""}` : d.label;
  return (
    <div className="relative flex h-3 w-3 items-center justify-center cursor-pointer">
      <CenterHandles layout={d.layout} />
      <div
        className={isVuln ? "h-2.5 w-2.5 rotate-45" : "h-2 w-2 rounded-sm"}
        style={{ background: isVuln ? color : "#27272A", border: `1.5px solid ${color}`, boxShadow: selected || isVuln ? `0 0 8px ${color}` : "none" }}
      />
      <OrientedLabel text={label} angle={d.angle} layout={d.layout} offset={10} color={color} className="ag-child-label text-[9px]" />
    </div>
  );
});

const nodeTypes = {
  root: RootNode,
  cluster: GroupNode,
  host: HostNode,
  more: MoreNode,
  "more-groups": MoreNode,
  port: ChildNode,
  vulnerability: ChildNode,
  certificate: ChildNode,
  child: ChildNode,
};

// ---------------------------------------------------------------------------
// HEAT meter — bottom-left threat level indicator
// ---------------------------------------------------------------------------

function HeatMeter({ vulnCount, criticalCount }: { vulnCount: number; criticalCount: number }) {
  const heat = Math.min(10, Math.floor(criticalCount * 3 + vulnCount * 0.5));
  const heatColor = heat >= 7 ? "#F05151" : heat >= 4 ? "#F8B925" : BRAND;
  return (
    <div className="flex items-center gap-2 rounded border px-3 py-1.5" style={{ borderColor: `${heatColor}44`, background: "#141414dd" }}>
      <span className=" text-[11px] font-semibold uppercase" style={{ color: heatColor }}>HEAT</span>
      <div className="flex gap-0.5">
        {Array.from({ length: 10 }, (_, i) => (
          <div key={i} className="h-2 w-1.5 rounded-sm" style={{ background: i < heat ? heatColor : "#292929", boxShadow: i < heat ? `0 0 4px ${heatColor}66` : "none" }} />
        ))}
      </div>
      <span className="font-mono text-[9px]" style={{ color: heatColor }}>{heat}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Side panel — host / group / finding details
// ---------------------------------------------------------------------------

type Selection = { kind: "host"; host: HostRecord } | { kind: "group"; group: GroupRecord } | { kind: "child"; data: any } | null;

function IntelPanel({
  sel,
  onClose,
  onPickHost,
  shownInGraph,
  onShowMore,
}: {
  sel: NonNullable<Selection>;
  onClose: () => void;
  onPickHost: (h: HostRecord) => void;
  /** Hosts of the selected group currently drawn in the graph. */
  shownInGraph?: number;
  onShowMore?: (key: string) => void;
}) {
  const color =
    sel.kind === "host" ? sevColor(sel.host.worst) : sel.kind === "group" ? sevColor(sel.group.worst) : sevColor(sel.data.severity);
  return (
    <motion.div
      initial={{ x: 20, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 20, opacity: 0 }}
      className="absolute top-0 right-0 z-20 h-full w-80 overflow-y-auto border-l"
      style={{ borderColor: `${color}33`, background: "#141414f2" }}
    >
      <div className="flex items-center justify-between border-b px-4 py-3" style={{ borderColor: `${color}22` }}>
        <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: BRAND }}>
          {sel.kind === "group" ? "Group intel" : "Node intel"}
        </span>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground" aria-label="Close details">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {sel.kind === "host" && (
        <div className="space-y-4 px-4 py-3">
          <div>
            <span className="text-[11px] uppercase text-muted-foreground">Host</span>
            <p className="mt-0.5 break-all font-mono text-xs" style={{ color }}>{sel.host.label}</p>
          </div>
          {sel.host.ips.length > 0 && (
            <div>
              <span className="text-[11px] uppercase text-muted-foreground">IPs</span>
              {sel.host.ips.map((ip) => (
                <p key={ip} className="mt-0.5 font-mono text-xs text-foreground/80">{ip}</p>
              ))}
            </div>
          )}
          <div>
            <span className="text-[11px] uppercase text-muted-foreground">Findings ({sel.host.findings.length})</span>
            {sel.host.findings.length === 0 && <p className="mt-1 font-mono text-[10px] text-muted-foreground">None found</p>}
            <div className="mt-1 space-y-1">
              {[...sel.host.findings]
                .sort((a, b) => SEVERITIES.indexOf(a.severity) - SEVERITIES.indexOf(b.severity))
                .map((f) => (
                  <div key={f.id} className="flex items-center justify-between gap-2 rounded px-2 py-1" style={{ background: "#292929" }}>
                    <span className="truncate font-mono text-[10px] text-foreground">{f.label}</span>
                    <span className="shrink-0 rounded px-1 font-mono text-[9px] font-semibold uppercase" style={{ color: SEVERITY_COLOR[f.severity], background: `${SEVERITY_COLOR[f.severity]}22` }}>
                      {f.severity}
                    </span>
                  </div>
                ))}
            </div>
          </div>
          <div>
            <span className="text-[11px] uppercase text-muted-foreground">Open ports ({sel.host.ports.length})</span>
            <div className="mt-1 space-y-1">
              {sel.host.ports.slice(0, 30).map((p) => (
                <div key={p.port} className="flex items-center justify-between rounded px-2 py-1" style={{ background: "#292929" }}>
                  <span className="font-mono text-[10px] text-foreground">{p.port}</span>
                  <span className="font-mono text-[9px] text-muted-foreground">{p.service || "?"}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {sel.kind === "group" && (
        <div className="space-y-4 px-4 py-3">
          <div>
            <span className="text-[11px] uppercase text-muted-foreground">Group</span>
            <p className="mt-0.5 break-all font-mono text-xs" style={{ color: sel.group.worst ? color : "#D4D4D8" }}>{sel.group.label}</p>
            <p className="mt-1 font-mono text-[10px] text-muted-foreground">
              {sel.group.hosts.length} hosts · {sel.group.findingCount} findings
            </p>
            <div className="mt-1.5"><SevBar counts={sel.group.sevCounts} /></div>
            {shownInGraph !== undefined && shownInGraph < sel.group.hosts.length && onShowMore && (
              <button
                onClick={() => onShowMore(sel.group.key)}
                className="mt-2 w-full rounded border px-2 py-1 font-mono text-[10px] text-foreground hover:brightness-125"
                style={{ borderColor: "#3F3F46", background: "#1B1B1B" }}
              >
                Showing {shownInGraph} of {sel.group.hosts.length} in graph · show {Math.min(HOST_LIMIT_STEP, sel.group.hosts.length - shownInGraph)} more
              </button>
            )}
          </div>
          <div>
            <span className="text-[11px] uppercase text-muted-foreground">{sel.group.findingCount ? "Riskiest hosts" : "Hosts"}</span>
            <div className="mt-1 space-y-1">
              {sel.group.hosts.slice(0, 12).map((h) => (
                <button
                  key={h.id}
                  onClick={() => onPickHost(h)}
                  className="flex w-full items-center justify-between gap-2 rounded px-2 py-1 text-left hover:brightness-125"
                  style={{ background: "#292929" }}
                >
                  <span className="truncate font-mono text-[10px] text-foreground">{h.label}</span>
                  {h.findings.length > 0 && (
                    <span className="shrink-0 font-mono text-[9px] font-semibold" style={{ color: sevColor(h.worst) }}>
                      {h.findings.length}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {sel.kind === "child" && (
        <div className="space-y-3 px-4 py-3">
          <div>
            <span className="text-[11px] uppercase text-muted-foreground">{sel.data.type}</span>
            <p className="mt-0.5 break-all font-mono text-xs" style={{ color }}>{sel.data.label}</p>
          </div>
          {sel.data.severity && (
            <div>
              <span className="text-[11px] uppercase text-muted-foreground">Severity</span>
              <p className="mt-0.5 font-mono text-xs uppercase" style={{ color }}>{sel.data.severity}</p>
            </div>
          )}
          {sel.data.service && (
            <div>
              <span className="text-[11px] uppercase text-muted-foreground">Service</span>
              <p className="mt-0.5 font-mono text-xs text-foreground">{sel.data.service} {sel.data.version || ""}</p>
            </div>
          )}
          {sel.data.host && (
            <div>
              <span className="text-[11px] uppercase text-muted-foreground">Host</span>
              <p className="mt-0.5 break-all font-mono text-xs text-foreground/80">{sel.data.host}</p>
            </div>
          )}
          {sel.data.banner && (
            <div>
              <span className="text-[11px] uppercase text-muted-foreground">Banner</span>
              <p className="mt-0.5 break-all font-mono text-[10px] text-muted-foreground">{String(sel.data.banner).slice(0, 300)}</p>
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Graph canvas
// ---------------------------------------------------------------------------

const LOD_CSS = `
.ag-wrap[data-lod="far"] .ag-host-label,
.ag-wrap[data-lod="far"] .ag-child-label { display: none; }
`;

function GraphCanvas({
  view,
  layout,
  fitKey,
  focusId,
  selectedId,
  onNodeClick,
}: {
  view: ViewResult;
  layout: LayoutMode;
  fitKey: string;
  focusId: { id: string; n: number } | null;
  selectedId: string | null;
  onNodeClick: (node: Node) => void;
}) {
  const { fitView, setCenter, getZoom } = useReactFlow();
  const wrapRef = useRef<HTMLDivElement>(null);

  const nodes: Node[] = useMemo(
    () =>
      view.nodes.map((n) => ({
        id: n.id,
        // "group" is a reserved React Flow type with its own box styling.
        type: n.kind === "group" ? "cluster" : n.kind,
        position: { x: n.x, y: n.y },
        selected: n.id === selectedId,
        draggable: false,
        connectable: false,
        data: { ...n.data, kind: n.kind, angle: n.angle, layout },
      })),
    [view, layout, selectedId]
  );

  const edges: Edge[] = useMemo(
    () =>
      view.edges.map((e) => {
        const hot = e.severity === "critical" || e.severity === "high";
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          type: layout === "radial" ? "straight" : "default",
          selectable: false,
          style: {
            stroke: hot ? `${SEVERITY_COLOR[e.severity as Severity]}99` : e.severity && e.severity !== "info" ? `${SEVERITY_COLOR[e.severity]}55` : "#3F3F4688",
            strokeWidth: e.depth === 1 ? 1.6 : hot ? 1.3 : 0.8,
          },
        };
      }),
    [view, layout]
  );

  // Fit when the dataset / grouping / layout / search changes.
  useEffect(() => {
    const t = setTimeout(() => fitView({ padding: 0.25, minZoom: 0.45, duration: 350 }), 60);
    return () => clearTimeout(t);
  }, [fitKey, fitView]);

  // After expanding/collapsing, keep the clicked node in view.
  useEffect(() => {
    if (!focusId) return;
    const n = view.nodes.find((v) => v.id === focusId.id);
    if (!n) return;
    const t = setTimeout(() => setCenter(n.x, n.y, { zoom: Math.max(getZoom(), 0.55), duration: 350 }), 60);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusId]);

  // Level of detail: hide small labels when zoomed far out (set on the wrapper
  // so nodes do not re-render on every zoom step).
  useOnViewportChange({
    onChange: (vp) => {
      const el = wrapRef.current;
      if (!el) return;
      const lod = vp.zoom < 0.4 ? "far" : vp.zoom < 0.75 ? "mid" : "near";
      if (el.dataset.lod !== lod) el.dataset.lod = lod;
    },
  });

  return (
    <div ref={wrapRef} className="ag-wrap relative h-full w-full" data-lod="mid">
      <style>{LOD_CSS}</style>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        nodeOrigin={[0.5, 0.5]}
        onNodeClick={(_, n) => onNodeClick(n)}
        onlyRenderVisibleElements
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        minZoom={0.02}
        maxZoom={3}
        fitView
        fitViewOptions={{ padding: 0.25, minZoom: 0.45 }}
        proOptions={{ hideAttribution: true }}
        className="bg-transparent"
      >
        <Background variant={BackgroundVariant.Dots} gap={40} size={1} color="#29292944" />
        <Controls
          showZoom
          showFitView
          showInteractive={false}
          position="bottom-right"
          className="graph-controls !rounded !border"
          style={{ borderColor: "#292929", background: "#141414dd" }}
        />
      </ReactFlow>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

function Segmented<T extends string>({ value, options, onChange, label }: { value: T; options: { value: T; label: string; hint?: string }[]; onChange: (v: T) => void; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</span>
      <div className="flex rounded border p-0.5" style={{ borderColor: "#292929", background: "#1B1B1B" }} role="radiogroup" aria-label={label}>
        {options.map((o) => (
          <button
            key={o.value}
            role="radio"
            aria-checked={value === o.value}
            title={o.hint}
            onClick={() => onChange(o.value)}
            className={cn("rounded px-2 py-0.5 font-mono text-[10px] transition-colors", value === o.value ? "text-white" : "text-muted-foreground hover:text-foreground")}
            style={value === o.value ? { background: `${BRAND}cc` } : undefined}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function GraphContent() {
  const { markComplete } = useChecklistAutoComplete();
  const [scans, setScans] = useState<Scan[]>([]);
  const [selectedScanId, setSelectedScanId] = useState<string>("");
  const [loadingScans, setLoadingScans] = useState(true);
  const [graphData, setGraphData] = useState<any>(null);
  const [loadingGraph, setLoadingGraph] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [groupBy, setGroupBy] = useState<GroupBy>("risk");
  const [layout, setLayout] = useState<LayoutMode>("radial");
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [expandedHosts, setExpandedHosts] = useState<Set<string>>(new Set());
  const [hostLimits, setHostLimits] = useState<Record<string, number>>({});
  const [groupLimit, setGroupLimit] = useState(DEFAULT_GROUP_LIMIT);
  const [layers, setLayers] = useState<Record<string, boolean>>({ port: true, vulnerability: true, certificate: true });
  const [riskyOnly, setRiskyOnly] = useState(false);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [matchCursor, setMatchCursor] = useState(0);
  const [selection, setSelection] = useState<Selection>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focusId, setFocusId] = useState<{ id: string; n: number } | null>(null);
  const focusSeq = useRef(0);
  const focus = (id: string) => setFocusId({ id, n: ++focusSeq.current });

  useEffect(() => {
    const p = readPrefs();
    if (p.groupBy && GROUP_BY_OPTIONS.some((o) => o.value === p.groupBy)) setGroupBy(p.groupBy);
    if (p.layout === "radial" || p.layout === "tree") setLayout(p.layout);
  }, []);
  useEffect(() => writePrefs({ groupBy, layout }), [groupBy, layout]);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (selectedScanId) fetchGraph(selectedScanId);
  }, [selectedScanId, fetchGraph]);

  const index: GraphIndex | null = useMemo(() => indexGraph(graphData), [graphData]);

  // Reset disclosure state whenever the data or the grouping changes: open the
  // riskiest groups so threats are visible on first paint.
  useEffect(() => {
    if (!index) return;
    const groups = groupHosts(index.hosts, groupBy, index.root.label);
    setExpandedGroups(groups.length === 1 ? new Set([groups[0].key]) : defaultExpandedGroups(groups));
    setExpandedHosts(new Set());
    setHostLimits({});
    setGroupLimit(DEFAULT_GROUP_LIMIT);
    setSelection(null);
    setSelectedId(null);
  }, [index, groupBy]);

  // Debounce search typing.
  useEffect(() => {
    const t = setTimeout(() => {
      setSearch(searchInput);
      setMatchCursor(0);
    }, 200);
    return () => clearTimeout(t);
  }, [searchInput]);

  const view = useMemo(
    () =>
      index
        ? buildView(index, { groupBy, layout, expandedGroups, expandedHosts, hostLimits, groupLimit, layers, riskyOnly, search })
        : null,
    [index, groupBy, layout, expandedGroups, expandedHosts, hostLimits, groupLimit, layers, riskyOnly, search]
  );

  const stats = useMemo(() => {
    if (!index) return { hosts: 0, findings: 0, critical: 0 };
    let findings = 0;
    let critical = 0;
    for (const h of index.hosts) {
      findings += h.findings.length;
      critical += h.sevCounts.critical + h.sevCounts.high;
    }
    return { hosts: index.hosts.length, findings, critical };
  }, [index]);

  const toggleSet = (set: Set<string>, key: string) => {
    const next = new Set(set);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    return next;
  };

  const selectHost = useCallback(
    (h: HostRecord) => {
      if (!index || !view) return;
      const key = groupKeyOfHost(view.groups, h.id);
      if (key) {
        setExpandedGroups((s) => new Set(s).add(key));
        const g = view.groups.find((x) => x.key === key)!;
        const pos = g.hosts.findIndex((x) => x.id === h.id);
        if (pos >= DEFAULT_HOST_LIMIT) setHostLimits((l) => ({ ...l, [key]: Math.max(l[key] ?? DEFAULT_HOST_LIMIT, pos + 1) }));
        const gi = view.groups.findIndex((x) => x.key === key);
        if (gi >= groupLimit) setGroupLimit(gi + 1);
      }
      setSelection({ kind: "host", host: h });
      setSelectedId(h.id);
      focus(h.id);
    },
    [index, view, groupLimit]
  );

  const onNodeClick = useCallback(
    (node: Node) => {
      if (!index || !view) return;
      const d = node.data as any;
      switch (node.type) {
        case "cluster": {
          const g = view.groups.find((x) => x.key === d.key);
          if (!view.searching) setExpandedGroups((s) => toggleSet(s, d.key));
          if (g) setSelection({ kind: "group", group: g });
          setSelectedId(node.id);
          focus(node.id);
          break;
        }
        case "host": {
          const h = index.hostById.get(node.id);
          if (!h) break;
          if (h.children.length) setExpandedHosts((s) => toggleSet(s, h.id));
          setSelection({ kind: "host", host: h });
          setSelectedId(h.id);
          focus(h.id);
          break;
        }
        case "more":
          setHostLimits((l) => ({ ...l, [d.key]: (l[d.key] ?? DEFAULT_HOST_LIMIT) + HOST_LIMIT_STEP }));
          focus(groupNodeId(d.key));
          break;
        case "more-groups":
          setGroupLimit((n) => n + GROUP_LIMIT_STEP);
          break;
        case "root":
          setSelection(null);
          setSelectedId(null);
          break;
        default:
          setSelection({ kind: "child", data: d });
          setSelectedId(node.id);
      }
    },
    [index, view]
  );

  const expandRisky = () => {
    if (!view) return;
    setExpandedGroups(new Set(view.groups.filter((g) => g.worst && g.worst !== "info").map((g) => g.key)));
    setGroupLimit(Math.max(groupLimit, view.groups.filter((g) => g.worst && g.worst !== "info").length));
  };
  const collapseAll = () => {
    setExpandedGroups(new Set());
    setExpandedHosts(new Set());
    setHostLimits({});
  };

  const matches = view?.searching ? [...view.filteredHosts].sort((a, b) => a.label.localeCompare(b.label)) : [];
  const onSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchInput !== search) {
      setSearch(searchInput);
      return;
    }
    if (!matches.length) return;
    const h = matches[matchCursor % matches.length];
    setMatchCursor((c) => c + 1);
    selectHost(h);
  };

  const fitKey = `${selectedScanId}|${groupBy}|${layout}|${search}|${riskyOnly}|${index ? "1" : "0"}`;
  const layerTypes = index ? ["port", "vulnerability", "certificate"].filter((t) => index.childTypes.has(t)) : [];
  const LAYER_LABEL: Record<string, string> = { port: "Ports", vulnerability: "Findings", certificate: "Certificates" };

  return (
    <div className="flex h-[calc(100dvh-3.5rem)] flex-col overflow-hidden" style={{ background: "#0B0B0B" }}>
      {/* ── Toolbar ── */}
      <div className="shrink-0 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b px-6 py-2" style={{ borderColor: "#292929", background: "#141414ee" }}>
        <div className="flex items-center gap-4">
          <select
            value={selectedScanId}
            onChange={(e) => setSelectedScanId(e.target.value)}
            disabled={loadingScans}
            className="h-7 rounded border px-2 font-mono text-[11px] focus:outline-none"
            style={{ borderColor: "#292929", background: "#1B1B1B", color: BRAND }}
            aria-label="Scan"
          >
            {loadingScans && <option>Loading...</option>}
            {!loadingScans && scans.length === 0 && <option>No scans</option>}
            {scans.map((scan) => (
              <option key={scan.id} value={scan.id}>{scan.domain}</option>
            ))}
          </select>
          <div className="flex items-center gap-2">
            <span
              className="rounded px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider"
              style={{
                color: stats.critical > 0 ? "#F05151" : BRAND,
                background: stats.critical > 0 ? "#F0515115" : `${BRAND}15`,
                border: `1px solid ${stats.critical > 0 ? "#F0515133" : `${BRAND}33`}`,
              }}
            >
              {stats.critical > 0 ? "ALERT" : "SILENT"}
            </span>
            <span className="font-mono text-[10px] text-muted-foreground">
              {stats.critical > 0 ? `${stats.critical} critical/high findings` : "No critical or high findings"}
            </span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Segmented label="Group by" value={groupBy} options={GROUP_BY_OPTIONS} onChange={setGroupBy} />
          <Segmented
            label="Layout"
            value={layout}
            options={[{ value: "radial", label: "Radial" }, { value: "tree", label: "Tree" }]}
            onChange={setLayout}
          />
          <div className="flex items-center gap-1">
            <button onClick={expandRisky} title="Open every group that has findings" className="flex items-center gap-1 rounded border px-2 py-1 font-mono text-[10px] text-muted-foreground hover:text-foreground" style={{ borderColor: "#292929", background: "#1B1B1B" }}>
              <Maximize2 className="h-3 w-3" /> Expand risky
            </button>
            <button onClick={collapseAll} title="Collapse all groups" className="flex items-center gap-1 rounded border px-2 py-1 font-mono text-[10px] text-muted-foreground hover:text-foreground" style={{ borderColor: "#292929", background: "#1B1B1B" }}>
              <Minimize2 className="h-3 w-3" /> Collapse
            </button>
          </div>
          <form onSubmit={onSearchSubmit} className="flex items-center gap-1.5 rounded border px-2 py-1" style={{ borderColor: "#292929", background: "#1B1B1B" }}>
            <Search className="h-3 w-3" style={{ color: `${BRAND}99` }} />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Host, IP, port, finding…"
              className="h-5 w-44 bg-transparent font-mono text-[10px] focus:outline-none"
              style={{ color: "#E4E4E7" }}
              aria-label="Search the graph"
            />
            {search.trim() && (
              <span className="whitespace-nowrap font-mono text-[9px]" style={{ color: matches.length ? BRAND : "#F0515188" }}>
                {matches.length ? `${matches.length} match${matches.length === 1 ? "" : "es"} · ↵ next` : "no match"}
              </span>
            )}
            {searchInput && (
              <button type="button" onClick={() => setSearchInput("")} aria-label="Clear search" className="text-muted-foreground hover:text-foreground">
                <X className="h-3 w-3" />
              </button>
            )}
          </form>
        </div>
      </div>

      {/* ── Main area ── */}
      <div className="relative flex-1 overflow-hidden">
        {index && !loadingGraph && (
          <div className="absolute top-3 left-3 z-10 flex w-48 flex-col gap-2 rounded border p-2.5" style={{ borderColor: "#292929", background: "#141414ee", backdropFilter: "blur(8px)" }}>
            <span className="text-[11px] uppercase text-muted-foreground">Show</span>
            <label className="flex cursor-pointer items-center gap-2 font-mono text-[10px] text-foreground">
              <input type="checkbox" checked={riskyOnly} onChange={(e) => setRiskyOnly(e.target.checked)} className="accent-[#EC3C53]" />
              <Flame className="h-3 w-3" style={{ color: "#F67A31" }} /> Only hosts with findings
            </label>
            {layerTypes.map((t) => (
              <label key={t} className="flex cursor-pointer items-center gap-2 font-mono text-[10px] text-foreground">
                <input type="checkbox" checked={layers[t] !== false} onChange={(e) => setLayers((l) => ({ ...l, [t]: e.target.checked }))} className="accent-[#EC3C53]" />
                {LAYER_LABEL[t]} <span className="text-muted-foreground">(on open host)</span>
              </label>
            ))}
            <div className="mt-1 border-t pt-2" style={{ borderColor: "#292929" }}>
              <span className="text-[11px] uppercase text-muted-foreground">Severity</span>
              <div className="mt-1 grid grid-cols-2 gap-x-2 gap-y-1">
                {(["critical", "high", "medium", "low"] as Severity[]).map((s) => (
                  <span key={s} className="flex items-center gap-1.5 font-mono text-[10px] capitalize text-foreground/80">
                    <span className="h-2 w-2 rounded-full" style={{ background: SEVERITY_COLOR[s] }} /> {s}
                  </span>
                ))}
                <span className="flex items-center gap-1.5 font-mono text-[10px] text-foreground/80">
                  <span className="h-2 w-2 rounded-full border" style={{ borderColor: CLEAN }} /> clean
                </span>
              </div>
            </div>
            <p className="font-mono text-[9px] leading-snug text-muted-foreground">Click a group to open it, a host to see its ports and findings.</p>
          </div>
        )}

        {index && !loadingGraph && (
          <div className="absolute bottom-3 left-3 z-10">
            <HeatMeter vulnCount={stats.findings} criticalCount={stats.critical} />
          </div>
        )}

        {index && view && !loadingGraph && (
          <div className="absolute bottom-3 left-1/2 z-10 flex -translate-x-1/2 items-center gap-4 rounded border px-4 py-1.5" style={{ borderColor: "#292929", background: "#141414ee" }}>
            <span className="font-mono text-[10px] text-muted-foreground">
              Showing <span className="text-foreground">{view.nodes.length}</span> of {index.totalNodes} nodes
            </span>
            <span className="font-mono text-[10px]" style={{ color: "#D4D4D8" }}>
              {view.filteredHosts.length === stats.hosts ? `${stats.hosts} hosts` : `${view.filteredHosts.length} of ${stats.hosts} hosts`} in {view.groups.length} groups
            </span>
            <span className="font-mono text-[10px]" style={{ color: stats.findings ? "#F67A31" : CLEAN }}>{stats.findings} findings</span>
          </div>
        )}

        {error ? (
          <div className="flex h-full items-center justify-center">
            <div className="space-y-3 text-center">
              <Bug className="mx-auto h-8 w-8" style={{ color: "#F05151" }} />
              <p className="font-mono text-xs" style={{ color: "#F05151" }}>{error}</p>
              <Button variant="outline" size="sm" onClick={() => selectedScanId && fetchGraph(selectedScanId)} className="gap-1.5" style={{ borderColor: "#292929" }}>
                Retry
              </Button>
            </div>
          </div>
        ) : loadingGraph ? (
          <div className="flex h-full items-center justify-center">
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="h-6 w-6 animate-spin" style={{ color: BRAND }} />
              <p className="font-mono text-xs" style={{ color: `${BRAND}88` }}>Computing attack graph...</p>
            </div>
          </div>
        ) : !index || !view ? (
          <div className="flex h-full items-center justify-center">
            <div className="space-y-3 text-center">
              <Waypoints className="mx-auto h-10 w-10" style={{ color: "#292929" }} />
              <p className="font-mono text-xs text-muted-foreground">No graph data available</p>
            </div>
          </div>
        ) : (
          <ReactFlowProvider>
            <GraphCanvas view={view} layout={layout} fitKey={fitKey} focusId={focusId} selectedId={selectedId} onNodeClick={onNodeClick} />
            {view.searching && view.filteredHosts.length === 0 && (
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                <p className="rounded border px-3 py-2 font-mono text-xs text-muted-foreground" style={{ borderColor: "#292929", background: "#141414ee" }}>
                  No host matches “{search}”
                </p>
              </div>
            )}
          </ReactFlowProvider>
        )}

        <AnimatePresence>
          {selection && (
            <IntelPanel
              sel={selection}
              onClose={() => {
                setSelection(null);
                setSelectedId(null);
              }}
              onPickHost={selectHost}
              shownInGraph={
                selection.kind === "group" && (view?.searching || expandedGroups.has(selection.group.key))
                  ? Math.min(selection.group.hosts.length, hostLimits[selection.group.key] ?? DEFAULT_HOST_LIMIT)
                  : undefined
              }
              onShowMore={(key) => setHostLimits((l) => ({ ...l, [key]: (l[key] ?? DEFAULT_HOST_LIMIT) + HOST_LIMIT_STEP }))}
            />
          )}
        </AnimatePresence>
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
