import {
  buildView,
  defaultExpandedGroups,
  groupHosts,
  indexGraph,
  DEFAULT_GROUP_LIMIT,
  DEFAULT_HOST_LIMIT,
  MORE_GROUPS_ID,
  groupNodeId,
  moreNodeId,
  type ViewOptions,
} from "@/lib/attackGraphModel";

type N = { id: string; label: string; type: any; [k: string]: any };

/** Build a google.com-style payload: `n` hosts spread over `zones` zones. */
function payload(n: number, zones = 10, vulnEvery = 25) {
  const nodes: N[] = [{ id: "root", label: "example.com", type: "domain" }];
  const edges: { source: string; target: string }[] = [];
  for (let i = 0; i < n; i++) {
    const id = `h${i}`;
    const zone = `z${i % zones}`;
    nodes.push({
      id,
      label: `host${i}.${zone}.example.com`,
      type: "subdomain",
      ips: [`10.0.${i % 7}.${i % 250}`],
      ports: [{ port: 443, service: "https" }],
    });
    edges.push({ source: "root", target: id });
    nodes.push({ id: `${id}-port-443`, label: ":443", type: "port", port: 443 });
    edges.push({ source: id, target: `${id}-port-443` });
    if (i % vulnEvery === 0) {
      nodes.push({ id: `${id}-vuln`, label: "Exposed .git", type: "vulnerability", severity: i % 50 === 0 ? "critical" : "medium" });
      edges.push({ source: id, target: `${id}-vuln` });
    }
  }
  return { nodes, edges };
}

const opts = (o: Partial<ViewOptions> = {}): ViewOptions => ({
  groupBy: "risk",
  layout: "radial",
  expandedGroups: new Set(),
  expandedHosts: new Set(),
  hostLimits: {},
  groupLimit: DEFAULT_GROUP_LIMIT,
  layers: {},
  riskyOnly: false,
  search: "",
  ...o,
});

describe("attack graph model", () => {
  it("indexes hosts with their findings and worst severity", () => {
    const idx = indexGraph(payload(60) as any)!;
    expect(idx.hosts).toHaveLength(60);
    const h0 = idx.hostById.get("h0")!;
    expect(h0.findings).toHaveLength(1);
    expect(h0.worst).toBe("critical");
    expect(idx.hostById.get("h25")!.worst).toBe("medium");
    expect(idx.hostById.get("h1")!.worst).toBeNull();
    expect(idx.childTypes.has("port")).toBe(true);
  });

  it("collapsed view of a large scan is tiny", () => {
    const idx = indexGraph(payload(1200) as any)!;
    const v = buildView(idx, opts());
    // root + risk groups only
    expect(v.nodes.length).toBeLessThanOrEqual(7);
    expect(v.groups.reduce((n, g) => n + g.hosts.length, 0)).toBe(1200);
  });

  it("caps hosts in an expanded group and adds a +N more node", () => {
    const idx = indexGraph(payload(400) as any)!;
    const v = buildView(idx, opts({ expandedGroups: new Set(["clean"]) }));
    const hosts = v.nodes.filter((n) => n.kind === "host");
    expect(hosts).toHaveLength(DEFAULT_HOST_LIMIT);
    const more = v.nodes.find((n) => n.id === moreNodeId("clean"))!;
    expect(more.data.remaining).toBe(idx.hosts.filter((h) => !h.worst).length - DEFAULT_HOST_LIMIT);

    const v2 = buildView(idx, opts({ expandedGroups: new Set(["clean"]), hostLimits: { clean: 10_000 } }));
    expect(v2.nodes.find((n) => n.kind === "more")).toBeUndefined();
  });

  it("groups by name zone and folds single direct hosts together", () => {
    const p = payload(40, 4);
    p.nodes.push({ id: "w", label: "www.example.com", type: "subdomain" }, { id: "a", label: "api.example.com", type: "subdomain" });
    p.edges.push({ source: "root", target: "w" }, { source: "root", target: "a" });
    const idx = indexGraph(p as any)!;
    const groups = groupHosts(idx.hosts, "zone", "example.com");
    const labels = groups.map((g) => g.label);
    expect(labels).toContain("z0.example.com");
    expect(labels).toContain("Direct hosts (*.example.com)");
    expect(groups.find((g) => g.key === "@direct")!.hosts).toHaveLength(2);
  });

  it("folds groups beyond the limit into a +N more groups node", () => {
    const idx = indexGraph(payload(300, 40) as any)!;
    const v = buildView(idx, opts({ groupBy: "zone", groupLimit: 10 }));
    expect(v.nodes.filter((n) => n.kind === "group")).toHaveLength(10);
    expect(v.nodes.find((n) => n.id === MORE_GROUPS_ID)!.data.remaining).toBe(30);
  });

  it("search prunes to matching hosts and opens their groups", () => {
    const idx = indexGraph(payload(300) as any)!;
    const v = buildView(idx, opts({ search: "host12." }));
    const hosts = v.nodes.filter((n) => n.kind === "host");
    expect(hosts.map((h) => h.data.label)).toEqual(["host12.z2.example.com"]);
    expect(v.filteredHosts).toHaveLength(1);
  });

  it("risky-only filter keeps only hosts with findings", () => {
    const idx = indexGraph(payload(300) as any)!;
    const v = buildView(idx, opts({ riskyOnly: true }));
    expect(v.filteredHosts.every((h) => h.findings.length > 0)).toBe(true);
    expect(v.groups.find((g) => g.key === "clean")).toBeUndefined();
  });

  it("layer toggles prune children of an opened host", () => {
    const idx = indexGraph(payload(30) as any)!;
    const base = { expandedGroups: new Set(["critical"]), expandedHosts: new Set(["h0"]) };
    const all = buildView(idx, opts(base));
    expect(all.nodes.filter((n) => n.depth === 3).map((n) => n.kind).sort()).toEqual(["port", "vulnerability"]);
    const noPorts = buildView(idx, opts({ ...base, layers: { port: false } }));
    expect(noPorts.nodes.filter((n) => n.depth === 3).map((n) => n.kind)).toEqual(["vulnerability"]);
  });

  it("radial layout keeps sibling hosts apart", () => {
    const idx = indexGraph(payload(500) as any)!;
    const v = buildView(idx, opts({ expandedGroups: new Set(["clean"]), hostLimits: { clean: 200 } }));
    const hosts = v.nodes.filter((n) => n.kind === "host");
    let min = Infinity;
    for (let i = 1; i < hosts.length; i++) {
      min = Math.min(min, Math.hypot(hosts[i].x - hosts[i - 1].x, hosts[i].y - hosts[i - 1].y));
    }
    expect(min).toBeGreaterThanOrEqual(20);
    expect(v.edges.find((e) => e.source === "root" && e.target === groupNodeId("clean"))).toBeTruthy();
  });

  it("opens only the riskiest groups by default, within a budget", () => {
    const idx = indexGraph(payload(600, 30, 5) as any)!;
    const groups = groupHosts(idx.hosts, "zone", "example.com");
    const open = defaultExpandedGroups(groups);
    const shown = groups.filter((g) => open.has(g.key)).reduce((n, g) => n + Math.min(g.hosts.length, DEFAULT_HOST_LIMIT), 0);
    expect(open.size).toBeGreaterThan(0);
    expect(shown).toBeLessThanOrEqual(60);
  });
});
