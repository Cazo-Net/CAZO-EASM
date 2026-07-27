"""Graph analytics for blockchain transaction networks.

Uses NetworkX for in-memory graph algorithms:
- Community detection (Louvain)
- Centrality metrics (PageRank, betweenness)
- Shortest paths
- Cluster analysis

Optionally persists to Neo4j for large-scale analysis.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import networkx as nx

from app.schemas.blockchain import (
    Chain,
    GraphData,
    GraphEdge,
    GraphNode,
    RiskBand,
)

logger = logging.getLogger(__name__)


class TransactionGraph:
    """In-memory transaction graph with analytics capabilities."""

    def __init__(self) -> None:
        self._graph = nx.DiGraph()
        self._address_data: dict[str, dict[str, Any]] = {}

    def load_from_graph_data(self, data: GraphData) -> None:
        """Load a GraphData object into the NetworkX graph."""
        for node in data.nodes:
            self._graph.add_node(
                node.id,
                label=node.label,
                chain=node.chain.value,
                wallet_type=node.wallet_type.value,
                balance=float(node.balance) if node.balance else 0.0,
                risk_band=node.risk_band.value if node.risk_band else "unknown",
                entity_name=node.entity_name,
                tx_count=node.tx_count,
            )
            self._address_data[node.id] = {
                "label": node.label,
                "chain": node.chain,
                "wallet_type": node.wallet_type,
                "balance": node.balance,
                "risk_band": node.risk_band,
                "entity_name": node.entity_name,
                "tx_count": node.tx_count,
            }

        for edge in data.edges:
            if self._graph.has_edge(edge.source, edge.target):
                # Aggregate parallel edges
                existing = self._graph[edge.source][edge.target]
                existing["weight"] = existing.get("weight", 0) + float(edge.value) if edge.value else existing.get("weight", 0) + 1.0
                existing["tx_count"] = existing.get("tx_count", 0) + edge.tx_count
            else:
                self._graph.add_edge(
                    edge.source,
                    edge.target,
                    value=float(edge.value) if edge.value else 0.0,
                    weight=float(edge.value) if edge.value else 1.0,
                    tx_count=edge.tx_count,
                )

    def load_from_txs(
        self,
        txs: list[dict[str, Any]],
        chain: Chain,
        center_address: str = "",
    ) -> None:
        """Load transactions directly into the graph."""
        for tx in txs:
            from_addr = tx.get("from", "")
            to_addr = tx.get("to", "")
            value = float(tx.get("value", "0") or "0")
            tx_count = 1

            if not from_addr or not to_addr:
                continue

            for addr in (from_addr, to_addr):
                if addr not in self._graph:
                    self._graph.add_node(
                        addr,
                        label="center" if addr == center_address else "",
                        chain=chain.value,
                        balance=0.0,
                        tx_count=0,
                    )

            if self._graph.has_edge(from_addr, to_addr):
                existing = self._graph[from_addr][to_addr]
                existing["weight"] = existing.get("weight", 0) + value
                existing["tx_count"] = existing.get("tx_count", 0) + 1
            else:
                self._graph.add_edge(from_addr, to_addr, weight=value, tx_count=tx_count)

    # ── Centrality ─────────────────────────────────────────────────────

    def pagerank(self, top_n: int = 20) -> list[dict[str, Any]]:
        """Compute PageRank centrality."""
        if len(self._graph) == 0:
            return []

        try:
            pr = nx.pagerank(self._graph, alpha=0.85, max_iter=100)
        except nx.PowerIterationFailedConvergence:
            pr = {n: 1.0 / len(self._graph) for n in self._graph}

        ranked = sorted(pr.items(), key=lambda x: x[1], reverse=True)[:top_n]
        return [
            {
                "address": addr,
                "score": round(score, 6),
                **self._address_data.get(addr, {}),
            }
            for addr, score in ranked
        ]

    def betweenness_centrality(self, top_n: int = 20) -> list[dict[str, Any]]:
        """Compute betweenness centrality (bridge nodes)."""
        if len(self._graph) == 0:
            return []

        try:
            bc = nx.betweenness_centrality(self._graph, normalized=True)
        except Exception:
            return []

        ranked = sorted(bc.items(), key=lambda x: x[1], reverse=True)[:top_n]
        return [
            {
                "address": addr,
                "score": round(score, 6),
                **self._address_data.get(addr, {}),
            }
            for addr, score in ranked
        ]

    def degree_centrality(self, top_n: int = 20) -> list[dict[str, Any]]:
        """Compute degree centrality."""
        if len(self._graph) == 0:
            return []

        dc = nx.degree_centrality(self._graph)
        ranked = sorted(dc.items(), key=lambda x: x[1], reverse=True)[:top_n]
        return [
            {
                "address": addr,
                "score": round(score, 6),
                **self._address_data.get(addr, {}),
            }
            for addr, score in ranked
        ]

    # ── Community Detection ────────────────────────────────────────────

    def detect_communities(self) -> list[list[str]]:
        """Detect communities using Louvain method."""
        if len(self._graph) == 0:
            return []

        try:
            import networkx.algorithms.community as nx_comm
            undirected = self._graph.to_undirected()
            communities = nx_comm.louvain_communities(undirected, resolution=1.0)
            return [sorted(list(c)) for c in communities]
        except Exception as e:
            logger.debug("Community detection failed: %s", e)
            return []

    # ── Path Finding ──────────────────────────────────────────────────

    def shortest_path(
        self, source: str, target: str, max_hops: int = 10
    ) -> list[str] | None:
        """Find shortest path between two addresses."""
        try:
            path = nx.shortest_path(self._graph, source, target)
            if len(path) <= max_hops + 1:
                return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass
        return None

    def neighbors(
        self, address: str, depth: int = 1, direction: str = "both"
    ) -> dict[str, Any]:
        """Get neighbors of an address up to a given depth."""
        if address not in self._graph:
            return {"address": address, "neighbors": [], "edges": []}

        if direction == "in":
            neighbors = set(nx.ancestors(self._graph, address))
        elif direction == "out":
            neighbors = set(nx.descendants(self._graph, address))
        else:
            neighbors = set(nx.ancestors(self._graph, address)) | set(nx.descendants(self._graph, address))

        neighbor_nodes = []
        neighbor_edges = []

        for n in neighbors:
            if n in self._graph:
                node_data = self._graph.nodes[n]
                neighbor_nodes.append({
                    "address": n,
                    **node_data,
                })

        # Get edges between address and its neighbors
        for _, target, data in self._graph.out_edges(address, data=True):
            if target in neighbors:
                neighbor_edges.append({
                    "source": address,
                    "target": target,
                    **data,
                })
        for source, _, data in self._graph.in_edges(address, data=True):
            if source in neighbors:
                neighbor_edges.append({
                    "source": source,
                    "target": address,
                    **data,
                })

        return {
            "address": address,
            "neighbors": neighbor_nodes[:100],  # Cap at 100
            "edges": neighbor_edges[:200],
            "total_neighbors": len(neighbors),
        }

    # ── Export ─────────────────────────────────────────────────────────

    def to_graph_data(self) -> GraphData:
        """Export the NetworkX graph back to GraphData."""
        from app.schemas.blockchain import WalletType

        nodes = []
        for nid, data in self._graph.nodes(data=True):
            chain_val = data.get("chain", "ethereum")
            try:
                chain_enum = Chain(chain_val)
            except ValueError:
                chain_enum = Chain.ETHEREUM

            nodes.append(GraphNode(
                id=nid,
                label=data.get("label", ""),
                chain=chain_enum,
                balance=str(data.get("balance", 0)),
                entity_name=data.get("entity_name"),
                tx_count=data.get("tx_count", 0),
            ))

        edges = []
        for src, tgt, data in self._graph.edges(data=True):
            edges.append(GraphEdge(
                source=src,
                target=tgt,
                value=str(data.get("value", 0)),
                tx_count=data.get("tx_count", 0),
                weight=data.get("weight", 1.0),
            ))

        return GraphData(nodes=nodes, edges=edges)

    @property
    def node_count(self) -> int:
        return len(self._graph)

    @property
    def edge_count(self) -> int:
        return len(self._graph.edges)

    def summary(self) -> dict[str, Any]:
        """Return graph statistics."""
        if len(self._graph) == 0:
            return {"nodes": 0, "edges": 0, "density": 0, "components": 0}

        undirected = self._graph.to_undirected()
        return {
            "nodes": self.node_count,
            "edges": self.edge_count,
            "density": round(nx.density(self._graph), 6),
            "components": nx.number_weakly_connected_components(self._graph),
            "is_dag": nx.is_directed_acyclic_graph(self._graph),
        }
