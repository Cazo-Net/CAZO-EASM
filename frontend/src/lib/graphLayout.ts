import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  forceX,
  forceY,
  type SimulationNodeDatum,
} from "d3-force";

export interface PortSummary {
  port: number;
  state?: string;
  service?: string | null;
  version?: string | null;
  banner?: string | null;
}

export interface RawGraphNode {
  id: string;
  label: string;
  type: "domain" | "subdomain" | "port" | "vulnerability" | "certificate";
  ips?: string[];
  service?: string | null;
  severity?: string;
  // Enriched fields from the backend graph endpoint:
  ports?: PortSummary[];
  port_count?: number;
  vuln_count?: number;
  port?: number;
  state?: string;
  version?: string | null;
  banner?: string | null;
  host?: string;
  os_detection?: any;
  host_scripts?: any;
}

export interface RawGraphEdge {
  source: string;
  target: string;
  label?: string;
}

interface SimNode extends SimulationNodeDatum, RawGraphNode {
  // x, y, vx, vy provided by d3-force
}

interface SimLink {
  source: string;
  target: string;
}

const NODE_RADIUS: Record<string, number> = {
  domain: 46,
  subdomain: 34,
  port: 22,
  vulnerability: 20,
  certificate: 26,
};

/**
 * Compute a force-directed layout for the attack graph.
 *
 * Uses d3-force with:
 *  - many-body repulsion so nodes spread apart
 *  - link forces so connected nodes stay near each other
 *  - a radial pull toward the root so the domain anchors as the hub
 *  - collision so nodes (and labels) don't overlap
 *
 * The simulation runs a fixed number of ticks once, then is stopped — React
 * Flow owns all subsequent interaction (pan/zoom), so this stays cheap even
 * for 100+ nodes.
 */
export function computeForceLayout(
  rawNodes: RawGraphNode[],
  rawEdges: RawGraphEdge[]
): { positions: Map<string, { x: number; y: number }>; width: number; height: number } {
  const positions = new Map<string, { x: number; y: number }>();

  if (!rawNodes.length) {
    return { positions, width: 0, height: 0 };
  }

  const nodes: SimNode[] = rawNodes.map((n) => ({ ...n }));
  const links: SimLink[] = rawEdges.map((e) => ({ source: e.source, target: e.target }));

  const root = nodes.find((n) => n.type === "domain") || nodes[0];
  void root;
  const radiusFor = (n: SimNode) => NODE_RADIUS[n.type] || 24;

  const sim = forceSimulation<SimNode>(nodes)
    .force(
      "link",
      forceLink<SimNode, SimLink>(links)
        .id((d) => d.id)
        .distance((l) => {
          const srcId = typeof l.source === "string" ? l.source : (l.source as any).id;
          const s = nodes.find((n) => n.id === srcId);
          // shorter links for domain<->subdomain, longer for leaf nodes
          if (s && s.type === "domain") return 220;
          return 120;
        })
        .strength(0.5)
    )
    .force("charge", forceManyBody<SimNode>().strength((n) => (n.type === "domain" ? -1600 : -420)))
    .force("center", forceCenter(0, 0).strength(0.04))
    .force("collide", forceCollide<SimNode>().radius((n) => radiusFor(n as SimNode) + 26).strength(0.9))
    .force("x", forceX<SimNode>(0).strength((n) => (n.type === "domain" ? 0.18 : 0.02)))
    .force("y", forceY<SimNode>(0).strength((n) => (n.type === "domain" ? 0.18 : 0.02)))
    .stop();

  const tickCount = rawNodes.length > 80 ? 400 : 300;
  sim.tick(tickCount);

  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;

  nodes.forEach((n) => {
    const x = n.x ?? 0;
    const y = n.y ?? 0;
    positions.set(n.id, { x, y });
    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minY = Math.min(minY, y);
    maxY = Math.max(maxY, y);
  });

  const width = maxX - minX || 1000;
  const height = maxY - minY || 1000;

  return { positions, width, height };
}
