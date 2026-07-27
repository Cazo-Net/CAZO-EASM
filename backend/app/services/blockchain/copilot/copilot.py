"""Blockchain investigation copilot.

Translates natural language queries into structured operations:
- Graph queries (Cypher for Neo4j, or NetworkX operations)
- Risk assessments
- Attribution lookups
- Bridge tracing
- Clustering analysis
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from app.schemas.blockchain import Chain, CopilotQuery, CopilotResponse, Evidence

logger = logging.getLogger(__name__)


@dataclass
class ParsedIntent:
    action: str  # risk, attribution, trace, cluster, bridge, graph, search
    address: str | None = None
    chain: Chain = Chain.ETHEREUM
    params: dict[str, Any] | None = None
    raw_query: str = ""


# ── Intent Parsing ──────────────────────────────────────────────────────────

_ADDR_RE = re.compile(r"(0x[0-9a-fA-F]{40}|[13][a-km-zA-HJ-NP-Z1-9]{25,62}|bc1[a-zA-HJ-NP-Z0-9]{25,90})")
_CHAIN_KEYWORDS = {
    "ethereum": Chain.ETHEREUM, "eth": Chain.ETHEREUM,
    "bitcoin": Chain.BITCOIN, "btc": Chain.BITCOIN,
    "polygon": Chain.POLYGON, "matic": Chain.POLYGON,
    "arbitrum": Chain.ARBITRUM, "arb": Chain.ARBITRUM,
    "optimism": Chain.OPTIMISM, "op": Chain.OPTIMISM,
    "base": Chain.BASE,
    "avalanche": Chain.AVALANCHE, "avax": Chain.AVALANCHE,
    "bnb": Chain.BNB, "bsc": Chain.BNB,
}
_ACTION_KEYWORDS = {
    "risk": ["risk", "danger", "safe", "threat", "scam", "sanction"],
    "attribution": ["who", "entity", "name", "owner", "belongs", "owned by", "attribution"],
    "trace": ["trace", "follow", "path", "flow", "where did", "sent to", "received from"],
    "cluster": ["cluster", "group", "same wallet", "related", "connected"],
    "bridge": ["bridge", "cross-chain", "layer 2", "l2", "wrapped"],
    "graph": ["graph", "neighbors", "network", "connections", "topology"],
    "search": ["search", "find", "look up", "lookup", "query"],
}


def _detect_chain(text: str) -> Chain:
    text_lower = text.lower()
    for keyword, chain in _CHAIN_KEYWORDS.items():
        if keyword in text_lower:
            return chain
    return Chain.ETHEREUM


def _detect_action(text: str) -> str:
    text_lower = text.lower()
    for action, keywords in _ACTION_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return action
    return "search"


def parse_query(query: CopilotQuery) -> ParsedIntent:
    """Parse a natural language query into a structured intent."""
    text = query.question
    address = query.address
    chain = query.chain

    # Try to extract address from question if not provided
    if not address:
        addr_match = _ADDR_RE.search(text)
        if addr_match:
            address = addr_match.group(0)

    # Detect chain from question text
    detected_chain = _detect_chain(text)
    if detected_chain != Chain.ETHEREUM or "ethereum" in text.lower() or "eth" in text.lower():
        chain = detected_chain

    action = _detect_action(text)

    return ParsedIntent(
        action=action,
        address=address,
        chain=chain,
        raw_query=text,
    )


# ── Query Execution ─────────────────────────────────────────────────────────

async def _execute_risk(intent: ParsedIntent) -> dict[str, Any]:
    """Execute a risk assessment query."""
    from app.services.blockchain.risk import compute_risk

    if not intent.address:
        return {"error": "No address provided"}

    risk = await compute_risk(intent.address, intent.chain)
    return risk.model_dump(mode="json")


async def _execute_attribution(intent: ParsedIntent) -> dict[str, Any]:
    """Execute an attribution query."""
    from app.services.blockchain.attribution import attribute_address

    if not intent.address:
        return {"error": "No address provided"}

    attr = await attribute_address(intent.address, intent.chain)
    return attr.model_dump(mode="json")


async def _execute_trace(intent: ParsedIntent) -> dict[str, Any]:
    """Execute a trace/flow query."""
    from app.services.blockchain.providers.base import registry

    if not intent.address:
        return {"error": "No address provided"}

    provider = registry.get(intent.chain)
    if not provider:
        return {"error": f"Chain not supported: {intent.chain.value}"}

    txs = await provider.get_transactions(intent.address, page=1, page_size=20)
    return {
        "address": intent.address,
        "chain": intent.chain.value,
        "recent_transactions": [tx.model_dump(mode="json") for tx in txs],
        "trace_depth": "1 hop",
    }


async def _execute_cluster(intent: ParsedIntent) -> dict[str, Any]:
    """Execute a clustering query."""
    from app.services.blockchain.clustering import cluster_address

    if not intent.address:
        return {"error": "No address provided"}

    cluster = await cluster_address(intent.address, intent.chain)
    return cluster.model_dump(mode="json")


async def _execute_bridge(intent: ParsedIntent) -> dict[str, Any]:
    """Execute a bridge tracking query."""
    from app.services.blockchain.bridges import (
        detect_bridge_interactions,
        get_bridge_info,
        is_bridge_address,
    )

    if not intent.address:
        return {"error": "No address provided"}

    is_bridge = is_bridge_address(intent.address)
    bridge_info = get_bridge_info(intent.address)
    interactions = await detect_bridge_interactions(intent.address, intent.chain)

    return {
        "address": intent.address,
        "is_known_bridge": is_bridge,
        "bridge_info": bridge_info,
        "interactions": interactions,
    }


async def _execute_graph(intent: ParsedIntent) -> dict[str, Any]:
    """Execute a graph/network query."""
    from app.services.blockchain.providers.base import registry
    from app.services.blockchain.graph.analytics import TransactionGraph

    if not intent.address:
        return {"error": "No address provided"}

    provider = registry.get(intent.chain)
    if not provider:
        return {"error": f"Chain not supported: {intent.chain.value}"}

    graph_data = await provider.get_graph_data(intent.address, depth=1, limit=30)
    graph = TransactionGraph()
    graph.load_from_graph_data(graph_data)

    return {
        "address": intent.address,
        "graph_summary": graph.summary(),
        "pagerank_top5": graph.pagerank(top_n=5),
        "communities": graph.detect_communities()[:5],
    }


async def _execute_search(intent: ParsedIntent) -> dict[str, Any]:
    """Execute a search query."""
    from app.services.blockchain.labels.curated import get_curated_labels

    results = []
    if intent.address:
        for label in get_curated_labels(intent.chain):
            if label.entity_name and intent.address.lower() in (label.entity_name or "").lower():
                results.append(label.model_dump(mode="json"))

    return {"results": results, "query": intent.raw_query}


_EXECUTORS = {
    "risk": _execute_risk,
    "attribution": _execute_attribution,
    "trace": _execute_trace,
    "cluster": _execute_cluster,
    "bridge": _execute_bridge,
    "graph": _execute_graph,
    "search": _execute_search,
}


# ── Main Copilot Interface ──────────────────────────────────────────────────

async def ask_copilot(query: CopilotQuery) -> CopilotResponse:
    """Process a natural language investigation query."""
    intent = parse_query(query)

    executor = _EXECUTORS.get(intent.action, _execute_search)
    try:
        result = await executor(intent)
    except Exception as e:
        logger.error("Copilot execution failed: %s", e)
        result = {"error": str(e)}

    # Build answer string
    if isinstance(result, dict) and "error" in result:
        answer = f"I couldn't process that query: {result['error']}"
    elif intent.action == "risk":
        score = result.get("score", 0)
        band = result.get("band", "unknown")
        answer = f"Risk assessment: score {score}/100 ({band} risk)."
        factors = result.get("factors", [])
        if factors:
            answer += " Key factors: " + ", ".join(
                f.get("label", f.get("name", "unknown")) for f in factors[:3]
            ) + "."
    elif intent.action == "attribution":
        entity = result.get("entity_name") or result.get("entity")
        category = result.get("category", "unknown")
        confidence = result.get("confidence", 0)
        if entity:
            answer = f"This address belongs to {entity} ({category}, {confidence}% confidence)."
        else:
            answer = "No entity attribution found for this address."
    elif intent.action == "cluster":
        heuristics = result.get("heuristics", [])
        confidence = result.get("confidence", 0)
        if heuristics:
            answer = f"Clustering analysis found {len(heuristics)} heuristic(s) with {confidence:.0%} confidence."
        else:
            answer = "No clustering signals found for this address."
    elif intent.action == "bridge":
        is_bridge = result.get("is_known_bridge", False)
        interactions = result.get("interactions", [])
        if is_bridge:
            info = result.get("bridge_info", {})
            answer = f"This is a known bridge contract: {info.get('name', 'unknown')}."
        elif interactions:
            answer = f"Found {len(interactions)} bridge interaction(s)."
        else:
            answer = "No bridge interactions detected."
    else:
        answer = f"Query processed. Action: {intent.action}."

    return CopilotResponse(
        answer=answer,
        query_used=intent.raw_query,
        confidence=0.8 if intent.address else 0.3,
    )
