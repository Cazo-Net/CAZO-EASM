"""Blockchain Intelligence API routes.

Uses consolidated services: schemas, providers, labels, attribution, risk.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas.blockchain import (
    Chain,
    EntityCategory,
    PaginatedResponse,
    RiskBand,
    SearchResult,
)
from app.services.blockchain.attribution import attribute_address
from app.services.blockchain.labels.curated import get_curated_labels, lookup_address
from app.services.blockchain.providers.base import registry
from app.services.blockchain.risk import compute_risk

logger = logging.getLogger(__name__)

router = APIRouter()

_ETH_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_BTC_ADDRESS_RE = re.compile(r"^(1|3|bc1)[a-zA-HJ-NP-Z0-9]{25,62}$")


def _detect_chain(address: str) -> Chain | None:
    if _ETH_ADDRESS_RE.match(address):
        return Chain.ETHEREUM
    if _BTC_ADDRESS_RE.match(address):
        return Chain.BITCOIN
    return None


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/chains")
async def supported_chains():
    return {
        "chains": [c.value for c in registry.available_chains],
        "primary": "ethereum",
    }


@router.get("/wallet/{address}")
async def get_wallet(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    provider = registry.get(chain)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Chain not supported: {chain.value}")

    try:
        wallet = await provider.get_wallet_summary(address)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Wallet lookup failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch wallet data")

    attribution, risk = await asyncio.gather(
        attribute_address(address, chain),
        compute_risk(address, chain),
        return_exceptions=True,
    )

    return {
        "wallet": wallet.model_dump(mode="json"),
        "attribution": attribution.model_dump(mode="json") if attribution and not isinstance(attribution, Exception) else None,
        "risk": risk.model_dump(mode="json") if risk and not isinstance(risk, Exception) else None,
    }


@router.get("/wallet/{address}/transactions")
async def get_transactions(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    provider = registry.get(chain)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Chain not supported: {chain.value}")

    try:
        txs = await provider.get_transactions(address, page, page_size)
        return PaginatedResponse(
            items=[tx.model_dump(mode="json") for tx in txs],
            total=len(txs) + page * page_size,
            page=page,
            page_size=page_size,
            has_next=len(txs) == page_size,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Transaction fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch transactions")


@router.get("/transaction/{tx_hash}")
async def get_transaction(
    tx_hash: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    provider = registry.get(chain)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Chain not supported: {chain.value}")

    try:
        tx = await provider.get_transaction(tx_hash)
        return tx.model_dump(mode="json")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Transaction fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch transaction")


@router.get("/contract/{address}")
async def get_contract(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    provider = registry.get(chain)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Chain not supported: {chain.value}")

    try:
        contract = await provider.get_contract_detail(address)
        if not contract:
            raise HTTPException(status_code=404, detail="Address is not a contract")
        return contract.model_dump(mode="json")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Contract fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch contract data")


@router.get("/wallet/{address}/tokens")
async def get_token_balances(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    provider = registry.get(chain)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Chain not supported: {chain.value}")

    try:
        tokens = await provider.get_token_balances(address)
        return {"tokens": [t.model_dump(mode="json") for t in tokens]}
    except Exception as e:
        logger.error("Token balance fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch token balances")


@router.get("/wallet/{address}/risk")
async def get_risk_score(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    try:
        risk = await compute_risk(address, chain)
        return risk.model_dump(mode="json")
    except Exception as e:
        logger.error("Risk scoring failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to compute risk score")


@router.get("/wallet/{address}/attribution")
async def get_attribution(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    try:
        attribution = await attribute_address(address, chain)
        return attribution.model_dump(mode="json")
    except Exception as e:
        logger.error("Attribution failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to attribute wallet")


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, max_length=200),
    chain: Chain | None = Query(default=None),
):
    results: list[dict[str, Any]] = []
    query_lower = q.lower()

    for entry in get_curated_labels(chain):
        if entry.entity_name and query_lower in entry.entity_name.lower():
            results.append({
                "type": "entity",
                "entity_name": entry.entity_name,
                "category": entry.category.value,
                "confidence": entry.confidence,
            })

    chains_to_search = [chain] if chain else [Chain.ETHEREUM, Chain.BITCOIN]
    for c in chains_to_search:
        provider = registry.get(c)
        if provider and provider.is_available():
            if _ETH_ADDRESS_RE.match(q) and c == Chain.ETHEREUM:
                results.append({
                    "type": "address",
                    "value": q,
                    "chain": c.value,
                    "label": f"Ethereum address {q[:10]}...",
                })
            elif _BTC_ADDRESS_RE.match(q) and c == Chain.BITCOIN:
                results.append({
                    "type": "address",
                    "value": q,
                    "chain": c.value,
                    "label": f"Bitcoin address {q[:12]}...",
                })

    return {"results": results, "total": len(results)}


# ── Phase 2: Clustering ─────────────────────────────────────────────────────

@router.get("/wallet/{address}/cluster")
async def get_cluster(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    """Run clustering heuristics on an address."""
    from app.services.blockchain.clustering import cluster_address
    try:
        cluster = await cluster_address(address, chain)
        return cluster.model_dump(mode="json")
    except Exception as e:
        logger.error("Clustering failed: %s", e)
        raise HTTPException(status_code=500, detail="Clustering analysis failed")


# ── Phase 2: Bridge Tracking ────────────────────────────────────────────────

@router.get("/wallet/{address}/bridges")
async def get_bridge_interactions(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    """Detect bridge interactions for an address."""
    from app.services.blockchain.bridges import (
        detect_bridge_interactions,
        get_bridge_info,
        is_bridge_address,
    )
    try:
        is_bridge = is_bridge_address(address)
        bridge_info = get_bridge_info(address)
        interactions = await detect_bridge_interactions(address, chain)
        return {
            "address": address,
            "is_known_bridge": is_bridge,
            "bridge_info": bridge_info,
            "interactions": interactions,
        }
    except Exception as e:
        logger.error("Bridge detection failed: %s", e)
        raise HTTPException(status_code=500, detail="Bridge detection failed")


@router.get("/wallet/{address}/bridge-volume")
async def get_bridge_volume(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    """Get aggregate bridge volume for an address."""
    from app.services.blockchain.bridges import get_bridge_volume
    try:
        volume = await get_bridge_volume(address, chain)
        return volume
    except Exception as e:
        logger.error("Bridge volume failed: %s", e)
        raise HTTPException(status_code=500, detail="Bridge volume computation failed")


@router.get("/bridges/known")
async def list_known_bridges(
    source_chain: Chain | None = Query(default=None),
    dest_chain: Chain | None = Query(default=None),
):
    """List known bridge contracts."""
    from app.services.blockchain.bridges import get_known_bridges
    bridges = get_known_bridges(source_chain, dest_chain)
    return {
        "bridges": [
            {
                "source_chain": b["source_chain"].value,
                "dest_chain": b["dest_chain"].value,
                "contract_address": b["contract_address"],
                "bridge_type": b["bridge_type"].value,
                "name": b["name"],
            }
            for b in bridges
        ],
        "total": len(bridges),
    }


# ── Phase 2: Graph Analytics ────────────────────────────────────────────────

@router.get("/wallet/{address}/graph")
async def get_graph_analytics(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
    depth: int = Query(default=1, ge=1, le=3),
):
    """Get graph analytics for an address's transaction network."""
    from app.services.blockchain.graph.analytics import TransactionGraph
    provider = registry.get(chain)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Chain not supported: {chain.value}")
    try:
        graph_data = await provider.get_graph_data(address, depth=depth, limit=50)
        graph = TransactionGraph()
        graph.load_from_graph_data(graph_data)
        return {
            "summary": graph.summary(),
            "pagerank": graph.pagerank(top_n=10),
            "betweenness": graph.betweenness_centrality(top_n=10),
            "communities": graph.detect_communities()[:5],
            "neighbors": graph.neighbors(address, depth=depth),
        }
    except Exception as e:
        logger.error("Graph analytics failed: %s", e)
        raise HTTPException(status_code=500, detail="Graph analytics failed")


# ── Phase 2: ML Risk ────────────────────────────────────────────────────────

@router.get("/wallet/{address}/anomaly")
async def get_anomaly_score(
    address: str,
    chain: Chain = Chain.ETHEREUM,
):
    """Get ML-based anomaly score for a wallet."""
    from app.services.blockchain.ml.anomaly import AnomalyScorer, _extract_features, explain_anomaly
    provider = registry.get(chain)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Chain not supported: {chain.value}")
    try:
        txs = await provider.get_transactions(address, page=1, page_size=100)
        tx_dicts = [tx.model_dump(mode="json") for tx in txs]
        features = _extract_features(address, tx_dicts)
        scorer = AnomalyScorer()
        result = scorer.score(features)
        explanation = explain_anomaly(features, result.get("feature_importances", {}))
        return {
            "address": address,
            "chain": chain.value,
            "anomaly_score": result["anomaly_score"],
            "explanation": explanation,
            "feature_importances": result.get("feature_importances", {}),
            "model_version": result.get("model_version"),
            "status": result.get("status"),
        }
    except Exception as e:
        logger.error("Anomaly scoring failed: %s", e)
        raise HTTPException(status_code=500, detail="Anomaly scoring failed")


# ── Phase 2: Monitoring ─────────────────────────────────────────────────────

@router.post("/watches")
async def create_watch(body: dict[str, Any]):
    """Create a watch for an address."""
    from app.services.blockchain.monitoring.alerts import create_watch
    from fastapi import Body as FastAPIBody
    try:
        watch = create_watch(
            org_id=body.get("org_id", ""),
            user_id=body.get("user_id", ""),
            address=body.get("address", ""),
            chain=Chain(body.get("chain", "ethereum")),
            alert_on_new_tx=body.get("alert_on_new_tx", True),
            alert_on_risk_change=body.get("alert_on_risk_change", True),
            risk_threshold=body.get("risk_threshold"),
            webhook_url=body.get("webhook_url"),
            email_alert=body.get("email_alert", False),
        )
        return watch.model_dump(mode="json")
    except Exception as e:
        logger.error("Watch creation failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create watch")


@router.get("/watches")
async def list_watches(
    org_id: str | None = Query(default=None),
    address: str | None = Query(default=None),
):
    """List watches."""
    from app.services.blockchain.monitoring.alerts import list_watches
    watches = list_watches(org_id, address)
    return {"watches": [w.model_dump(mode="json") for w in watches]}


@router.delete("/watches/{watch_id}")
async def delete_watch(watch_id: str):
    """Delete a watch."""
    from app.services.blockchain.monitoring.alerts import delete_watch
    deleted = delete_watch(watch_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Watch not found")
    return {"deleted": True}


@router.get("/alerts")
async def list_alerts(
    org_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    unacknowledged_only: bool = Query(default=False),
):
    """List alerts."""
    from app.services.blockchain.monitoring.alerts import list_alerts
    alerts = list_alerts(org_id=org_id, user_id=user_id, unacknowledged_only=unacknowledged_only)
    return {"alerts": [a.model_dump(mode="json") for a in alerts]}


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, body: dict[str, Any]):
    """Acknowledge an alert."""
    from app.services.blockchain.monitoring.alerts import acknowledge_alert
    user_id = body.get("user_id", "")
    acknowledged = acknowledge_alert(alert_id, user_id)
    if not acknowledged:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"acknowledged": True}


# ── Phase 2: Copilot ────────────────────────────────────────────────────────

@router.post("/copilot/ask")
async def copilot_ask(body: dict[str, Any]):
    """Ask the investigation copilot a natural language question."""
    from app.services.blockchain.copilot.copilot import ask_copilot
    from app.schemas.blockchain import CopilotQuery
    try:
        query = CopilotQuery(
            question=body.get("question", ""),
            address=body.get("address", ""),
            chain=Chain(body.get("chain", "ethereum")),
        )
        response = await ask_copilot(query)
        return response.model_dump(mode="json")
    except Exception as e:
        logger.error("Copilot failed: %s", e)
        raise HTTPException(status_code=500, detail="Copilot query failed")


# ── Phase 2: Cases ──────────────────────────────────────────────────────────

@router.post("/cases")
async def create_case(body: dict[str, Any]):
    """Create a new investigation case."""
    from app.services.blockchain.cases.cases import create_case
    try:
        case = create_case(
            org_id=body.get("org_id", ""),
            title=body.get("title", ""),
            created_by=body.get("created_by", ""),
            description=body.get("description", ""),
            assigned_to=body.get("assigned_to"),
        )
        return case.model_dump(mode="json")
    except Exception as e:
        logger.error("Case creation failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create case")


@router.get("/cases")
async def list_cases(
    org_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    """List investigation cases."""
    from app.services.blockchain.cases.cases import list_cases, CaseStatus
    case_status = CaseStatus(status) if status else None
    cases = list_cases(org_id=org_id, status=case_status)
    return {"cases": [c.model_dump(mode="json") for c in cases]}


@router.get("/cases/{case_id}")
async def get_case(case_id: str):
    """Get a case with annotations, members, and audit trail."""
    from app.services.blockchain.cases.cases import (
        get_case, list_annotations, list_members, get_audit_trail,
    )
    case = get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return {
        "case": case.model_dump(mode="json"),
        "annotations": [a.model_dump(mode="json") for a in list_annotations(case_id)],
        "members": [m.model_dump(mode="json") for m in list_members(case_id)],
        "audit": [e.model_dump(mode="json") for e in get_audit_trail(case_id)],
    }


@router.put("/cases/{case_id}")
async def update_case(case_id: str, body: dict[str, Any]):
    """Update a case."""
    from app.services.blockchain.cases.cases import update_case, CaseStatus
    case_status = CaseStatus(body["status"]) if body.get("status") else None
    case = update_case(
        case_id=case_id,
        user_id=body.get("user_id", ""),
        title=body.get("title"),
        description=body.get("description"),
        status=case_status,
        assigned_to=body.get("assigned_to"),
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case.model_dump(mode="json")


@router.post("/cases/{case_id}/annotations")
async def add_annotation(case_id: str, body: dict[str, Any]):
    """Add an annotation to a case."""
    from app.services.blockchain.cases.cases import add_annotation
    ann = add_annotation(
        case_id=case_id,
        user_id=body.get("user_id", ""),
        content=body.get("content", ""),
        entity_type=body.get("entity_type", "address"),
        entity_id=body.get("entity_id", ""),
    )
    if not ann:
        raise HTTPException(status_code=404, detail="Case not found")
    return ann.model_dump(mode="json")


@router.post("/cases/{case_id}/members")
async def add_member(case_id: str, body: dict[str, Any]):
    """Add a member to a case."""
    from app.services.blockchain.cases.cases import add_member, CaseMemberRole
    role = CaseMemberRole(body.get("role", "analyst"))
    member = add_member(
        case_id=case_id,
        user_id=body.get("user_id", ""),
        role=role,
        added_by=body.get("added_by"),
    )
    if not member:
        raise HTTPException(status_code=404, detail="Case not found")
    return member.model_dump(mode="json")


@router.get("/cases/stats")
async def case_stats(org_id: str = Query(...)):
    """Get case statistics."""
    from app.services.blockchain.cases.cases import case_stats
    return case_stats(org_id)


@router.get("/alerts/stats")
async def alert_stats(org_id: str = Query(...)):
    """Get alert statistics."""
    from app.services.blockchain.monitoring.alerts import alert_stats
    return alert_stats(org_id)


# ── Phase 2: External Intel ─────────────────────────────────────────────────

@router.get("/wallet/{address}/intel")
async def get_external_intel(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    """Get external intelligence for an address (OFAC, Etherscan labels, etc.)."""
    from app.services.blockchain.intel import get_external_intel
    try:
        intel = await get_external_intel(address)
        return intel
    except Exception as e:
        logger.error("External intel failed: %s", e)
        raise HTTPException(status_code=500, detail="External intel lookup failed")


@router.get("/wallet/{address}/sanctions")
async def check_sanctions(address: str):
    """Check an address against OFAC sanctions list."""
    from app.services.blockchain.intel import check_ofac_sanctions
    try:
        result = await check_ofac_sanctions(address)
        return result or {"is_sanctioned": False}
    except Exception as e:
        logger.error("Sanctions check failed: %s", e)
        raise HTTPException(status_code=500, detail="Sanctions check failed")
