"""Attack Surface Graph Intelligence.

Builds and queries relationship graphs between assets:
- Organization → Domain → Subdomain → IP → ASN → Cloud Provider
- Technology → Vulnerability → Risk
- Supply chain: Vendor → Technology → Subdomain → Data flow
- Historical relationship evolution
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class GraphNode:
    id: str
    type: str  # organization, domain, subdomain, ip, asn, cloud, technology, vulnerability, vendor, data_flow
    label: str
    properties: Dict[str, Any] = field(default_factory=dict)
    risk_score: float = 0.0


@dataclass
class GraphEdge:
    source: str
    target: str
    relationship: str  # owns, resolves_to, hosted_on, uses, has_vulnerability, collects_data, injects_script
    confidence: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)


class AttackSurfaceGraph:
    """In-memory graph for attack surface relationships."""

    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self._adjacency: Dict[str, List[GraphEdge]] = defaultdict(list)

    def add_node(self, node: GraphNode) -> None:
        self.nodes[node.id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        self.edges.append(edge)
        self._adjacency[edge.source].append(edge)
        self._adjacency[edge.target].append(edge)

    def get_neighbors(self, node_id: str, relationship: Optional[str] = None) -> List[Tuple[GraphNode, GraphEdge]]:
        neighbors = []
        for edge in self._adjacency.get(node_id, []):
            if relationship and edge.relationship != relationship:
                continue
            other_id = edge.target if edge.source == node_id else edge.source
            other_node = self.nodes.get(other_id)
            if other_node:
                neighbors.append((other_node, edge))
        return neighbors

    def get_path(self, start: str, end: str, max_depth: int = 5) -> Optional[List[Tuple[GraphNode, GraphEdge]]]:
        """BFS path finding between two nodes."""
        if start not in self.nodes or end not in self.nodes:
            return None

        visited = {start}
        queue = [([self.nodes[start], ], [])]

        for path_nodes, path_edges in queue:
            current = path_nodes[-1].id
            if current == end:
                result = []
                for i, node in enumerate(path_nodes):
                    result.append((node, path_edges[i - 1] if i > 0 else None))
                return result

            if len(path_nodes) > max_depth:
                continue

            for neighbor, edge in self.get_neighbors(current):
                if neighbor.id not in visited:
                    visited.add(neighbor.id)
                    queue.append((path_nodes + [neighbor], path_edges + [edge]))

        return None

    def propagate_risk(self) -> None:
        """Propagate risk scores through the graph (high-risk parents boost children)."""
        for node in self.nodes.values():
            if node.risk_score > 0:
                for neighbor, edge in self.get_neighbors(node.id):
                    # Boost neighbor risk based on edge confidence
                    boost = node.risk_score * edge.confidence * 0.3
                    neighbor.risk_score = min(100, neighbor.risk_score + boost)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.__dict__ for n in self.nodes.values()],
            "edges": [e.__dict__ for e in self.edges],
            "summary": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "node_types": list(set(n.type for n in self.nodes.values())),
                "edge_types": list(set(e.relationship for e in self.edges)),
            },
        }

    def get_attack_surface_map(self) -> Dict[str, Any]:
        """Generate a visual attack surface map grouped by type."""
        by_type: Dict[str, List[Dict]] = defaultdict(list)
        for node in self.nodes.values():
            by_type[node.type].append({
                "id": node.id,
                "label": node.label,
                "risk": node.risk_score,
                "properties": node.properties,
            })

        relationships = []
        for edge in self.edges:
            source = self.nodes.get(edge.source)
            target = self.nodes.get(edge.target)
            if source and target:
                relationships.append({
                    "from": source.label,
                    "to": target.label,
                    "type": edge.relationship,
                    "confidence": edge.confidence,
                })

        return {
            "assets": dict(by_type),
            "relationships": relationships,
            "high_risk_nodes": [
                {"id": n.id, "label": n.label, "risk": n.risk_score}
                for n in sorted(self.nodes.values(), key=lambda x: x.risk_score, reverse=True)
                if n.risk_score > 50
            ],
        }

    # ── Supply Chain Analysis ────────────────────────────────────────────────

    def get_supply_chain_map(self) -> Dict[str, Any]:
        """Generate a supply chain risk map showing vendor → technology → domain flows."""
        vendors: Dict[str, Dict[str, Any]] = {}
        data_flows: List[Dict[str, Any]] = []
        script_injections: List[Dict[str, Any]] = []
        risk_propagation: List[Dict[str, Any]] = []

        # Build vendor map
        for node in self.nodes.values():
            if node.type == "vendor":
                vendors[node.id] = {
                    "name": node.label,
                    "risk_score": node.risk_score,
                    "properties": node.properties,
                    "technologies": [],
                    "connected_domains": [],
                }

        # Map vendor → technologies → domains
        for edge in self.edges:
            source_node = self.nodes.get(edge.source)
            target_node = self.nodes.get(edge.target)
            if not source_node or not target_node:
                continue

            # vendor → technology
            if source_node.type == "vendor" and target_node.type == "technology":
                if source_node.id in vendors:
                    vendors[source_node.id]["technologies"].append(target_node.label)

            # vendor → subdomain (direct data flow) OR technology → subdomain
            if (source_node.type == "vendor" and target_node.type == "subdomain") or \
               (source_node.type == "technology" and target_node.type == "subdomain"):
                vendor_type = source_node.properties.get("vendor_type", "")
                category = source_node.properties.get("category", "")
                is_vendor = source_node.type == "vendor"

                # For vendor nodes, get info from properties
                if is_vendor:
                    vendor_name = source_node.label
                    vendor_type = source_node.properties.get("vendor_type", "third_party_service")
                    category = source_node.properties.get("category", "unknown")
                else:
                    vendor_name = source_node.label

                flow = {
                    "vendor": vendor_name,
                    "domain": target_node.label,
                    "vendor_type": vendor_type,
                    "category": category,
                    "relationship": edge.relationship,
                    "confidence": edge.confidence,
                }

                if vendor_type in ("third_party_service", "saas_platform"):
                    data_flows.append(flow)

                if category in ("Support", "A/B Testing", "Feature Flags", "Analytics",
                                "session_recording", "auto_capture", "chat_widget"):
                    script_injections.append(flow)

            # vulnerability → technology
            if source_node.type == "vulnerability" and target_node.type == "technology":
                risk_propagation.append({
                    "vulnerability": source_node.label,
                    "technology": target_node.label,
                    "risk_score": source_node.risk_score,
                })

        # Calculate supply chain risk summary
        total_vendors = len(vendors)
        high_risk_vendors = [v for v in vendors.values() if v["risk_score"] > 50]
        data_collecting_vendors = [v for v in vendors.values()
                                   if any(t.get("category") in ("Analytics", "session_recording")
                                          for t in [{"category": v["properties"].get("category", "")}])]

        return {
            "vendors": vendors,
            "data_flows": data_flows,
            "script_injections": script_injections,
            "risk_propagation": risk_propagation,
            "summary": {
                "total_vendors": total_vendors,
                "high_risk_vendor_count": len(high_risk_vendors),
                "high_risk_vendors": [{"name": v["name"], "risk": v["risk_score"]} for v in high_risk_vendors],
                "data_flow_count": len(data_flows),
                "script_injection_count": len(script_injections),
                "unique_domains_affected": len({f["domain"] for f in data_flows}),
            },
        }

    def get_critical_supply_chain_paths(self) -> List[Dict[str, Any]]:
        """Find critical paths from high-risk vendors to sensitive assets."""
        critical_paths = []

        # Find high-risk vendor nodes
        high_risk_vendors = [
            n for n in self.nodes.values()
            if n.type == "vendor" and n.risk_score > 50
        ]

        for vendor in high_risk_vendors:
            # BFS to find all reachable domains
            visited = set()
            queue = [(vendor.id, [])]

            while queue:
                current_id, path = queue.pop(0)
                if current_id in visited:
                    continue
                visited.add(current_id)

                current_node = self.nodes.get(current_id)
                if not current_node:
                    continue

                # If we reached a domain, record the path
                if current_node.type == "domain":
                    critical_paths.append({
                        "vendor": vendor.label,
                        "vendor_risk": vendor.risk_score,
                        "path_length": len(path),
                        "path": [
                            {"id": n.id, "type": n.type, "label": n.label}
                            for n in [self.nodes[p] for p in path if p in self.nodes]
                        ] + [{"id": current_node.id, "type": current_node.type, "label": current_node.label}],
                        "risk_chain": vendor.risk_score,
                    })
                    continue

                # Continue traversal
                for neighbor, edge in self.get_neighbors(current_id):
                    if neighbor.id not in visited:
                        queue.append((neighbor.id, path + [current_id]))

        # Sort by risk
        critical_paths.sort(key=lambda x: x["vendor_risk"], reverse=True)
        return critical_paths[:20]  # Top 20 paths

    def get_vendor_concentration_risk(self) -> Dict[str, Any]:
        """Analyze vendor concentration — too many services from one provider."""
        vendor_usage: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "count": 0, "domains": set(), "risk_score": 0, "categories": set()
        })

        for edge in self.edges:
            source = self.nodes.get(edge.source)
            target = self.nodes.get(edge.target)
            if not source or not target:
                continue

            if source.type == "technology" and target.type == "subdomain":
                vendor_name = source.label
                vendor_usage[vendor_name]["count"] += 1
                vendor_usage[vendor_name]["domains"].add(target.label)
                vendor_usage[vendor_name]["risk_score"] = max(
                    vendor_usage[vendor_name]["risk_score"],
                    source.risk_score,
                )
                cat = source.properties.get("category", "unknown")
                vendor_usage[vendor_name]["categories"].add(cat)

        # Convert sets to lists for JSON
        result = {}
        for vendor, data in vendor_usage.items():
            result[vendor] = {
                "usage_count": data["count"],
                "domains": list(data["domains"]),
                "risk_score": data["risk_score"],
                "categories": list(data["categories"]),
                "concentration_risk": "high" if data["count"] > 5 else ("medium" if data["count"] > 2 else "low"),
            }

        return {
            "vendors": result,
            "highest_concentration": max(
                result.items(), key=lambda x: x[1]["usage_count"]
            ) if result else None,
            "single_point_of_failure": [
                v for v, d in result.items()
                if d["usage_count"] > 3 and d["risk_score"] > 40
            ],
        }


def build_graph_from_scan(scan_data: Dict[str, Any], domain: str) -> AttackSurfaceGraph:
    """Build an attack surface graph from scan pipeline results."""
    graph = AttackSurfaceGraph()

    # Add domain node
    graph.add_node(GraphNode(
        id=f"domain:{domain}",
        type="domain",
        label=domain,
        properties={"domain": domain},
    ))

    # Add subdomains and IPs
    subdomains = scan_data.get("subdomains", [])
    if isinstance(subdomains, list):
        for sub in subdomains:
            sub_id = f"subdomain:{sub}"
            graph.add_node(GraphNode(
                id=sub_id, type="subdomain", label=sub,
                properties={"hostname": sub},
            ))
            graph.add_edge(GraphEdge(
                source=f"domain:{domain}", target=sub_id,
                relationship="contains", confidence=1.0,
            ))

    # Add technologies
    tech_data = scan_data.get("technologies", {})
    if isinstance(tech_data, dict):
        for host, techs in tech_data.items():
            tech_list = techs if isinstance(techs, list) else []
            for tech in tech_list:
                if isinstance(tech, dict):
                    tech_name = tech.get("name", "")
                    tech_id = f"technology:{tech_name}"
                    if tech_id not in graph.nodes:
                        graph.add_node(GraphNode(
                            id=tech_id, type="technology", label=tech_name,
                            properties=tech,
                        ))
                    sub_id = f"subdomain:{host}"
                    if sub_id in graph.nodes:
                        graph.add_edge(GraphEdge(
                            source=sub_id, target=tech_id,
                            relationship="uses", confidence=tech.get("confidence", 50) / 100,
                        ))

    # Add IPs from port scan
    port_data = scan_data.get("ports", {})
    if isinstance(port_data, dict):
        for host, port_list in port_data.items():
            if isinstance(port_list, list):
                for p in port_list:
                    if isinstance(p, dict):
                        ip = p.get("ip")
                        if ip:
                            ip_id = f"ip:{ip}"
                            if ip_id not in graph.nodes:
                                graph.add_node(GraphNode(
                                    id=ip_id, type="ip", label=ip,
                                    properties={"ip": ip},
                                ))
                            sub_id = f"subdomain:{host}"
                            if sub_id in graph.nodes:
                                graph.add_edge(GraphEdge(
                                    source=sub_id, target=ip_id,
                                    relationship="resolves_to", confidence=1.0,
                                ))

    # Add vulnerabilities
    findings = scan_data.get("security_findings", [])
    if isinstance(findings, list):
        for i, finding in enumerate(findings):
            if isinstance(finding, dict):
                vuln_id = f"vulnerability:{i}"
                graph.add_node(GraphNode(
                    id=vuln_id, type="vulnerability",
                    label=finding.get("detail", finding.get("type", "Unknown")),
                    properties=finding,
                    risk_score=finding.get("risk_contribution", 0),
                ))

    # ── Supply chain nodes ──────────────────────────────────────────────────

    # Build vendor nodes from detected technologies
    tech_data = scan_data.get("technologies", {})
    if isinstance(tech_data, dict):
        seen_vendors: Dict[str, Dict[str, Any]] = {}
        for host, techs in tech_data.items():
            tech_list = techs if isinstance(techs, list) else []
            for tech in tech_list:
                if not isinstance(tech, dict):
                    continue
                name = tech.get("name", "")
                vendor_type = tech.get("vendor_type", "")
                category = tech.get("category", "")

                # Only create vendor nodes for third-party services
                if vendor_type not in ("third_party_service", "saas_platform"):
                    continue

                vendor_id = f"vendor:{name}"
                if vendor_id not in seen_vendors:
                    seen_vendors[vendor_id] = {
                        "name": name,
                        "category": category,
                        "vendor_type": vendor_type,
                        "domains": set(),
                    }

                seen_vendors[vendor_id]["domains"].add(host)

        # Create vendor nodes and edges
        for vendor_id, vdata in seen_vendors.items():
            # Risk score based on category
            risk = 10  # Default
            if vdata["category"] in ("Analytics", "session_recording"):
                risk = 30
            elif vdata["category"] in ("Support", "chat_widget"):
                risk = 20
            elif vdata["category"] in ("Payment", "Authentication"):
                risk = 5
            elif vdata["category"] in ("Monitoring",):
                risk = 15

            graph.add_node(GraphNode(
                id=vendor_id,
                type="vendor",
                label=vdata["name"],
                properties={
                    "category": vdata["category"],
                    "vendor_type": vdata["vendor_type"],
                    "connected_domains": list(vdata["domains"]),
                    "risk_level": "high" if risk > 25 else ("medium" if risk > 10 else "low"),
                },
                risk_score=risk,
            ))

            # Connect vendor → subdomains
            for domain in vdata["domains"]:
                sub_id = f"subdomain:{domain}"
                if sub_id in graph.nodes:
                    graph.add_edge(GraphEdge(
                        source=vendor_id,
                        target=sub_id,
                        relationship="collects_data",
                        confidence=0.8,
                        properties={"vendor_type": vdata["vendor_type"]},
                    ))

    # Add supply chain findings
    sc_findings = scan_data.get("exposure_validation", {}).get("findings", [])
    if isinstance(sc_findings, list):
        for i, finding in enumerate(sc_findings):
            if isinstance(finding, dict) and finding.get("category") == "subdomain_takeover":
                details = finding.get("details", {})
                vuln_id = f"supply_chain_risk:{i}"
                graph.add_node(GraphNode(
                    id=vuln_id,
                    type="vulnerability",
                    label=f"Supply chain risk: {finding.get('description', '')[:80]}",
                    properties=finding,
                    risk_score=25,
                ))
                # Connect to affected subdomain
                subdomain = details.get("subdomain", "")
                if subdomain:
                    sub_id = f"subdomain:{subdomain}"
                    if sub_id in graph.nodes:
                        graph.add_edge(GraphEdge(
                            source=vuln_id,
                            target=sub_id,
                            relationship="targets",
                            confidence=0.9,
                        ))

    # Propagate risk
    graph.propagate_risk()

    return graph
