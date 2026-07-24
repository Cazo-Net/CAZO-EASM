"""Attack Surface Graph Intelligence.

Builds and queries relationship graphs between assets:
- Organization → Domain → Subdomain → IP → ASN → Cloud Provider
- Technology → Vulnerability → Risk
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
    type: str  # organization, domain, subdomain, ip, asn, cloud, technology, vulnerability
    label: str
    properties: Dict[str, Any] = field(default_factory=dict)
    risk_score: float = 0.0


@dataclass
class GraphEdge:
    source: str
    target: str
    relationship: str  # owns, resolves_to, hosted_on, uses, has_vulnerability
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

    # Propagate risk
    graph.propagate_risk()

    return graph
