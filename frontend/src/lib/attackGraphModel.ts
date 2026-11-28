/**
 * Attack graph view model.
 *
 * The raw `/assets/graph` payload is a flat list of nodes (domain, subdomain,
 * port, vulnerability, certificate) plus edges. Drawn as-is, a domain with a
 * few hundred subdomains becomes an unreadable force-directed cloud.
 *
 * This module turns the payload into a *hierarchy* that is shown with
 * progressive disclosure:
 *
 *   root domain -> groups (collapsible) -> hosts (capped, "+N more") -> ports / findings
 *
 * and lays it out deterministically (no physics) as either a radial tree or a
 * left-to-right tree. Everything here is pure so it can be unit tested and so
 * a 1,000+ host scan stays cheap: only what is visible is positioned.
 */
import type { PortSummary, RawGraphEdge, RawGraphNode } from "./graphLayout";

// ---------------------------------------------------------------------------
// Severity helpers
// ---------------------------------------------------------------------------

export type Severity = "critical" | "high" | "medium" | "low" | "info";
export const SEVERITIES: Severity[] = ["critical", "high", "medium", "low", "info"];

export const SEV_RANK: Record<Severity, number> = { critical: 4, high: 3, medium: 2, low: 1, info: 0 };

export function normSeverity(s?: string | null): Severity {
  const v = (s || "").toLowerCase();
  return v === "critical" || v === "high" || v === "medium" || v === "low" ? v : "info";
}

export type SevCounts = Record<Severity, number>;
const emptyCounts = (): SevCounts => ({ critical: 0, high: 0, medium: 0, low: 0, info: 0 });

function worstOf(counts: SevCounts): Severity | null {
  for (const s of SEVERITIES) if (counts[s] > 0) return s;
  return null;
}

/** Rank used for sorting; hosts/groups without any finding sort last (-1). */
export function riskRank(s: Severity | null): number {
  return s ? SEV_RANK[s] : -1;
}

// ---------------------------------------------------------------------------
// Index: hosts with their ports / findings
// ---------------------------------------------------------------------------

export interface Finding {
  id: string;
  label: string;
  severity: Severity;
}

export interface HostRecord {
  id: string;
  label: string;
  ips: string[];
  ports: PortSummary[];
  findings: Finding[];
  /** Raw child nodes (port / vulnerability / certificate) linked to this host. */
  children: RawGraphNode[];
  sevCounts: SevCounts;
  /** Worst finding severity, or null when the host has no findings at all. */
  worst: Severity | null;
  raw: RawGraphNode;
}

export interface GraphIndex {
  root: RawGraphNode;
  hosts: HostRecord[];
  hostById: Map<string, HostRecord>;
  /** Child node types present in the data (drives the layer toggles). */
  childTypes: Set<string>;
  totalNodes: number;
}

const HOST_TYPES = new Set(["subdomain"]);

export function indexGraph(data: { nodes?: RawGraphNode[]; edges?: RawGraphEdge[] } | null | undefined): GraphIndex | null {
  const nodes = data?.nodes || [];
  if (!nodes.length) return null;
  const edges = data?.edges || [];

  const root = nodes.find((n) => n.type === "domain") || nodes[0];
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const hostById = new Map<string, HostRecord>();
  const hosts: HostRecord[] = [];

  for (const n of nodes) {
    if (n === root) continue;
    // Extra domain nodes (multi-root payloads) are treated like hosts.
    if (!HOST_TYPES.has(n.type) && n.type !== "domain") continue;
    const h: HostRecord = {
      id: n.id,
      label: n.label || n.id,
      ips: Array.isArray(n.ips) ? n.ips : [],
      ports: Array.isArray(n.ports) ? [...n.ports] : [],
      findings: [],
      children: [],
      sevCounts: emptyCounts(),
      worst: null,
      raw: n,
    };
    hostById.set(n.id, h);
    hosts.push(h);
  }

  const childTypes = new Set<string>();
  const seenPorts = new Map<string, Set<number>>();
  for (const e of edges) {
    const host = hostById.get(e.source);
    const child = byId.get(e.target);
    if (!host || !child || hostById.has(child.id) || child === root) continue;
    host.children.push(child);
    childTypes.add(child.type);
    if (child.type === "vulnerability") {
      const sev = normSeverity(child.severity);
      host.findings.push({ id: child.id, label: child.label, severity: sev });
      host.sevCounts[sev] += 1;
    } else if (child.type === "port" && typeof child.port === "number") {
      // Older payloads have no `ports` summary on the host: rebuild it.
      let s = seenPorts.get(host.id);
      if (!s) seenPorts.set(host.id, (s = new Set(host.ports.map((p) => p.port))));
      if (!s.has(child.port)) {
        s.add(child.port);
        host.ports.push({ port: child.port, state: child.state, service: child.service, version: child.version });
      }
    }
  }
  for (const h of hosts) h.worst = worstOf(h.sevCounts);

  return { root, hosts, hostById, childTypes, totalNodes: nodes.length };
}

// ---------------------------------------------------------------------------
// Grouping
// ---------------------------------------------------------------------------

export type GroupBy = "risk" | "zone" | "network" | "service";

export const GROUP_BY_OPTIONS: { value: GroupBy; label: string; hint: string }[] = [
  { value: "risk", label: "Risk", hint: "Worst finding on each host" },
  { value: "zone", label: "Name", hint: "Parent zone, e.g. *.mail.example.com" },
  { value: "network", label: "Network", hint: "Same /24 IP range" },
  { value: "service", label: "Exposure", hint: "What the open ports expose" },
];

export interface GroupRecord {
  key: string;
  label: string;
  hosts: HostRecord[];
  sevCounts: SevCounts;
  worst: Severity | null;
  findingCount: number;
}

const RISK_GROUPS: { key: string; label: string }[] = [
  { key: "critical", label: "Critical findings" },
  { key: "high", label: "High findings" },
  { key: "medium", label: "Medium findings" },
  { key: "low", label: "Low findings" },
  { key: "info", label: "Informational only" },
  { key: "clean", label: "No findings" },
];

function zoneKey(label: string, rootLabel: string): { key: string; label: string; direct: boolean } {
  const host = label.toLowerCase().replace(/\.$/, "");
  const root = rootLabel.toLowerCase().replace(/\.$/, "");
  if (host === root) return { key: "@direct", label: `Direct hosts (*.${root})`, direct: true };
  if (host.endsWith("." + root)) {
    const parts = host.slice(0, -(root.length + 1)).split(".");
    const zone = parts[parts.length - 1];
    return { key: `z:${zone}`, label: `${zone}.${root}`, direct: parts.length === 1 };
  }
  const p = host.split(".");
  const base = p.slice(-2).join(".");
  return { key: `o:${base}`, label: base, direct: false };
}

function networkKey(ips: string[]): { key: string; label: string } {
  const v4 = ips.find((ip) => /^\d+\.\d+\.\d+\.\d+$/.test(ip));
  if (v4) {
    const p = v4.split(".");
    const k = `${p[0]}.${p[1]}.${p[2]}.0/24`;
    return { key: k, label: k };
  }
  const v6 = ips.find((ip) => ip.includes(":"));
  if (v6) {
    const k = v6.split(":").slice(0, 4).join(":") + "::/64";
    return { key: k, label: k };
  }
  return { key: "none", label: "Unresolved (no IP)" };
}

const DB_PORTS = new Set([1433, 1521, 3306, 5432, 5984, 6379, 7000, 9042, 9200, 9300, 11211, 27017, 27018]);
const REMOTE_PORTS = new Set([21, 22, 23, 445, 139, 2375, 2376, 3389, 5900, 5985, 5986]);
const MAIL_PORTS = new Set([25, 110, 143, 465, 587, 993, 995]);
const WEB_PORTS = new Set([80, 443, 8000, 8008, 8080, 8443, 8888, 3000, 5000, 9000, 9443]);

function serviceKey(ports: PortSummary[]): { key: string; label: string; order: number } {
  const nums = ports.map((p) => p.port);
  if (!nums.length) return { key: "none", label: "No open ports", order: 6 };
  if (nums.some((p) => DB_PORTS.has(p))) return { key: "db", label: "Databases exposed", order: 0 };
  if (nums.some((p) => REMOTE_PORTS.has(p))) return { key: "remote", label: "Remote access exposed", order: 1 };
  if (nums.some((p) => MAIL_PORTS.has(p))) return { key: "mail", label: "Mail servers", order: 2 };
  if (nums.every((p) => WEB_PORTS.has(p))) {
    return nums.some((p) => p !== 80 && p !== 443)
      ? { key: "web-alt", label: "Web (non-standard ports)", order: 3 }
      : { key: "web", label: "Web (80/443 only)", order: 4 };
  }
  return { key: "other", label: "Other services", order: 5 };
}

export function compareHosts(a: HostRecord, b: HostRecord): number {
  return (
    riskRank(b.worst) - riskRank(a.worst) ||
    b.findings.length - a.findings.length ||
    a.label.localeCompare(b.label)
  );
}

export function groupHosts(hosts: HostRecord[], by: GroupBy, rootLabel: string): GroupRecord[] {
  const map = new Map<string, { label: string; hosts: HostRecord[]; order: number }>();
  const add = (key: string, label: string, h: HostRecord, order = 0) => {
    let g = map.get(key);
    if (!g) map.set(key, (g = { label, hosts: [], order }));
    g.hosts.push(h);
  };

  for (const h of hosts) {
    if (by === "risk") {
      const key = h.worst || "clean";
      const idx = RISK_GROUPS.findIndex((r) => r.key === key);
      add(key, RISK_GROUPS[idx].label, h, idx);
    } else if (by === "zone") {
      const z = zoneKey(h.label, rootLabel);
      add(z.key, z.label, h);
    } else if (by === "network") {
      const n = networkKey(h.ips);
      add(n.key, n.label, h, n.key === "none" ? 1 : 0);
    } else {
      const s = serviceKey(h.ports);
      add(s.key, s.label, h, s.order);
    }
  }

  if (by === "zone") {
    // Single direct children (www.example.com, api.example.com …) would each
    // become a one-host group; fold them into one "Direct hosts" group.
    const direct = map.get("@direct") || { label: `Direct hosts (*.${rootLabel})`, hosts: [], order: 0 };
    for (const [key, g] of Array.from(map.entries())) {
      if (key === "@direct" || g.hosts.length !== 1) continue;
      if (zoneKey(g.hosts[0].label, rootLabel).direct) {
        direct.hosts.push(g.hosts[0]);
        map.delete(key);
      }
    }
    if (direct.hosts.length) map.set("@direct", direct);
  }

  const groups: (GroupRecord & { order: number })[] = [];
  for (const [key, g] of Array.from(map.entries())) {
    const sevCounts = emptyCounts();
    for (const h of g.hosts) for (const s of SEVERITIES) sevCounts[s] += h.sevCounts[s];
    g.hosts.sort(compareHosts);
    groups.push({
      key,
      label: g.label,
      hosts: g.hosts,
      sevCounts,
      worst: worstOf(sevCounts),
      findingCount: SEVERITIES.reduce((n, s) => n + sevCounts[s], 0),
      order: g.order,
    });
  }

  groups.sort((a, b) =>
    by === "risk" || by === "service"
      ? a.order - b.order
      : riskRank(b.worst) - riskRank(a.worst) ||
        b.findingCount - a.findingCount ||
        a.order - b.order ||
        b.hosts.length - a.hosts.length ||
        a.label.localeCompare(b.label)
  );
  return groups.map(({ order: _o, ...g }) => g);
}

// ---------------------------------------------------------------------------
// Filtering
// ---------------------------------------------------------------------------

export function hostMatches(h: HostRecord, q: string): boolean {
  if (!q) return true;
  if (h.label.toLowerCase().includes(q)) return true;
  if (h.ips.some((ip) => ip.includes(q))) return true;
  if (h.findings.some((f) => f.label.toLowerCase().includes(q))) return true;
  return h.ports.some((p) => String(p.port) === q.replace(/^:/, "") || (p.service || "").toLowerCase() === q);
}

// ---------------------------------------------------------------------------
// View building + layout
// ---------------------------------------------------------------------------

export type LayoutMode = "radial" | "tree";
export type ViewKind = "root" | "group" | "host" | "more" | "more-groups" | "port" | "vulnerability" | "certificate" | "child";

export interface ViewOptions {
  groupBy: GroupBy;
  layout: LayoutMode;
  expandedGroups: Set<string>;
  expandedHosts: Set<string>;
  /** Per-group number of hosts to show when expanded. */
  hostLimits: Record<string, number>;
  /** Number of groups to show before folding the rest into "+N more groups". */
  groupLimit: number;
  /** Child layers: port / vulnerability / certificate. Missing key = shown. */
  layers: Record<string, boolean>;
  riskyOnly: boolean;
  search: string;
}

export const DEFAULT_HOST_LIMIT = 30;
export const HOST_LIMIT_STEP = 60;
export const DEFAULT_GROUP_LIMIT = 16;
export const GROUP_LIMIT_STEP = 16;

export interface ViewNode {
  id: string;
  kind: ViewKind;
  x: number;
  y: number;
  depth: number;
  /** Direction from the root (radians) in radial mode; used to orient labels. */
  angle: number;
  data: Record<string, any>;
}

export interface ViewEdge {
  id: string;
  source: string;
  target: string;
  /** Worst severity of the target side, for edge colour. */
  severity: Severity | null;
  depth: number;
}

export interface ViewResult {
  nodes: ViewNode[];
  edges: ViewEdge[];
  groups: GroupRecord[];
  /** Hosts after risk/search filters. */
  filteredHosts: HostRecord[];
  visibleHosts: number;
  hiddenGroups: number;
  searching: boolean;
}

export const groupNodeId = (key: string) => `g:${key}`;
export const moreNodeId = (key: string) => `more:${key}`;
export const MORE_GROUPS_ID = "more-groups";

interface TNode {
  id: string;
  kind: ViewKind;
  weight: number;
  data: Record<string, any>;
  children: TNode[];
  severity: Severity | null;
  gapBefore?: number;
  depth?: number;
  slot?: number;
}

/** Spacing rules, in px, for each depth of the tree. */
const RADIAL_MIN_SPACING = [0, 120, 26, 22];
const RADIAL_RING_GAP = [0, 230, 200, 150];
const TREE_X = [0, 300, 640, 1010];
const TREE_ROW = 30;

export function buildView(index: GraphIndex, opts: ViewOptions): ViewResult {
  const q = opts.search.trim().toLowerCase();
  const searching = q.length > 0;

  let hosts = index.hosts;
  if (opts.riskyOnly) hosts = hosts.filter((h) => h.worst && SEV_RANK[h.worst] >= SEV_RANK.low);
  if (searching) hosts = hosts.filter((h) => hostMatches(h, q));

  const groups = groupHosts(hosts, opts.groupBy, index.root.label);
  const shownGroups = groups.slice(0, Math.max(1, opts.groupLimit));
  const hiddenGroups = groups.length - shownGroups.length;

  const root: TNode = {
    id: index.root.id,
    kind: "root",
    weight: 2,
    severity: null,
    data: { label: index.root.label, hostCount: hosts.length, totalHosts: index.hosts.length },
    children: [],
  };

  let visibleHosts = 0;
  shownGroups.forEach((g, gi) => {
    const expanded = searching || opts.expandedGroups.has(g.key);
    const gNode: TNode = {
      id: groupNodeId(g.key),
      kind: "group",
      weight: 2,
      severity: g.worst,
      gapBefore: gi === 0 ? 0 : 0.8,
      data: {
        key: g.key,
        label: g.label,
        hostCount: g.hosts.length,
        sevCounts: g.sevCounts,
        worst: g.worst,
        findingCount: g.findingCount,
        expanded,
      },
      children: [],
    };
    if (expanded) {
      const limit = opts.hostLimits[g.key] ?? DEFAULT_HOST_LIMIT;
      const shown = g.hosts.slice(0, limit);
      for (const h of shown) {
        visibleHosts += 1;
        const hostExpanded = opts.expandedHosts.has(h.id);
        const hNode: TNode = {
          id: h.id,
          kind: "host",
          weight: 1,
          severity: h.worst,
          data: {
            label: h.label,
            worst: h.worst,
            findingCount: h.findings.length,
            portCount: h.ports.length,
            ips: h.ips,
            match: searching,
            expanded: hostExpanded,
            hasChildren: h.children.length > 0,
          },
          children: [],
        };
        if (hostExpanded) {
          const kids = h.children
            .filter((c) => opts.layers[c.type] !== false)
            .sort((a, b) => {
              // findings first, worst first; then ports ascending
              const av = a.type === "vulnerability" ? 10 + SEV_RANK[normSeverity(a.severity)] : 0;
              const bv = b.type === "vulnerability" ? 10 + SEV_RANK[normSeverity(b.severity)] : 0;
              return bv - av || (a.port ?? 0) - (b.port ?? 0) || a.label.localeCompare(b.label);
            });
          for (const c of kids) {
            const kind: ViewKind =
              c.type === "port" || c.type === "vulnerability" || c.type === "certificate" ? c.type : "child";
            hNode.children.push({
              id: c.id,
              kind,
              weight: 1,
              severity: c.type === "vulnerability" ? normSeverity(c.severity) : null,
              data: { ...c, label: c.label, severity: c.type === "vulnerability" ? normSeverity(c.severity) : undefined },
              children: [],
            });
          }
        }
        gNode.children.push(hNode);
      }
      const rest = g.hosts.length - shown.length;
      if (rest > 0) {
        gNode.children.push({
          id: moreNodeId(g.key),
          kind: "more",
          weight: 1.6,
          severity: null,
          data: { key: g.key, remaining: rest, step: Math.min(rest, HOST_LIMIT_STEP) },
          children: [],
        });
      }
    }
    root.children.push(gNode);
  });

  if (hiddenGroups > 0) {
    const hiddenHostCount = groups.slice(shownGroups.length).reduce((n, g) => n + g.hosts.length, 0);
    root.children.push({
      id: MORE_GROUPS_ID,
      kind: "more-groups",
      weight: 2,
      severity: null,
      gapBefore: 0.8,
      data: { remaining: hiddenGroups, hosts: hiddenHostCount, step: Math.min(hiddenGroups, GROUP_LIMIT_STEP) },
      children: [],
    });
  }

  // ---- slot assignment (leaves get sequential slots, parents centred) ----
  let cursor = 0;
  const all: TNode[] = [];
  const assign = (n: TNode, depth: number) => {
    n.depth = depth;
    all.push(n);
    cursor += n.gapBefore || 0;
    if (!n.children.length) {
      n.slot = cursor + n.weight / 2;
      cursor += n.weight;
      return;
    }
    for (const c of n.children) assign(c, depth + 1);
    n.slot = (n.children[0].slot! + n.children[n.children.length - 1].slot!) / 2;
  };
  if (root.children.length) {
    for (const c of root.children) assign(c, 1);
    root.depth = 0;
    root.slot = 0;
    all.unshift(root);
  } else {
    root.depth = 0;
    root.slot = 0;
    all.push(root);
  }
  const totalSlots = Math.max(cursor, 1);

  // ---- projection ----
  const pos = new Map<string, { x: number; y: number; angle: number }>();
  if (opts.layout === "radial") {
    const maxDepth = all.reduce((m, n) => Math.max(m, n.depth!), 0);
    const radii: number[] = [0];
    for (let d = 1; d <= maxDepth; d++) {
      const slots = all.filter((n) => n.depth === d).map((n) => n.slot!).sort((a, b) => a - b);
      let minGap = totalSlots;
      for (let i = 1; i < slots.length; i++) minGap = Math.min(minGap, slots[i] - slots[i - 1]);
      if (slots.length > 1) minGap = Math.min(minGap, totalSlots - slots[slots.length - 1] + slots[0]);
      const needed = slots.length > 1 ? (RADIAL_MIN_SPACING[d] * totalSlots) / (2 * Math.PI * Math.max(minGap, 0.01)) : 0;
      radii[d] = Math.max(needed, radii[d - 1] + RADIAL_RING_GAP[Math.min(d, 3)], d === 1 ? 260 : 0);
    }
    // Start at the top (-90°) so the first (riskiest) group sits at 12 o'clock.
    for (const n of all) {
      if (n.depth === 0) {
        pos.set(n.id, { x: 0, y: 0, angle: 0 });
        continue;
      }
      const a = (n.slot! / totalSlots) * 2 * Math.PI - Math.PI / 2;
      const r = radii[n.depth!];
      pos.set(n.id, { x: Math.cos(a) * r, y: Math.sin(a) * r, angle: a });
    }
  } else {
    for (const n of all) {
      const y = n.depth === 0 ? (root.children.length ? ((root.children[0].slot! + root.children[root.children.length - 1].slot!) / 2) * TREE_ROW : 0) : n.slot! * TREE_ROW;
      pos.set(n.id, { x: TREE_X[Math.min(n.depth!, 3)] + Math.max(0, n.depth! - 3) * 300, y, angle: 0 });
    }
  }

  const nodes: ViewNode[] = [];
  const edges: ViewEdge[] = [];
  const walk = (n: TNode) => {
    const p = pos.get(n.id)!;
    nodes.push({ id: n.id, kind: n.kind, x: p.x, y: p.y, depth: n.depth!, angle: p.angle, data: n.data });
    for (const c of n.children) {
      edges.push({ id: `${n.id}->${c.id}`, source: n.id, target: c.id, severity: c.severity, depth: c.depth! });
      walk(c);
    }
  };
  walk(root);

  return { nodes, edges, groups, filteredHosts: hosts, visibleHosts, hiddenGroups, searching };
}

/**
 * Groups to open by default: the riskiest groups (critical / high findings),
 * as long as the hosts they reveal stay within a small budget so the first
 * view is never a hairball.
 */
export function defaultExpandedGroups(groups: GroupRecord[], budget = 60): Set<string> {
  const out = new Set<string>();
  let used = 0;
  const risky = groups
    .filter((g) => g.worst === "critical" || g.worst === "high")
    .sort((a, b) => riskRank(b.worst) - riskRank(a.worst) || b.findingCount - a.findingCount);
  for (const g of risky) {
    const cost = Math.min(g.hosts.length, DEFAULT_HOST_LIMIT);
    if (used > 0 && used + cost > budget) continue;
    out.add(g.key);
    used += cost;
  }
  return out;
}

/** Find which group a host falls into for the current grouping. */
export function groupKeyOfHost(groups: GroupRecord[], hostId: string): string | null {
  for (const g of groups) if (g.hosts.some((h) => h.id === hostId)) return g.key;
  return null;
}
