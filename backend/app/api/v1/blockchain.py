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
        "mock_mode": provider._needs_key() if hasattr(provider, '_needs_key') else False,
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


# ── Phase 3: Neo4j Graph Sync ─────────────────────────────────────────────────

from app.blockchain.application.graph_sync import graph_sync as _graph_sync
from app.blockchain.application.watchdog import watchdog as _watchdog
from app.blockchain.domain.value_objects.chain import Chain as GraphChain


@router.get("/graph/health")
async def graph_health():
    """Health check for the Neo4j-backed graph layer."""
    return await _graph_sync.health()


@router.post("/graph/sync/address")
async def graph_sync_address(body: dict[str, str]):
    """Trigger a full sync of an address into Neo4j."""
    chain = GraphChain(body.get("chain", "ethereum"))
    address = body.get("address", "")
    if not address:
        raise HTTPException(status_code=400, detail="address is required")
    try:
        result = await _graph_sync.sync_address(chain, address)
        return {"status": "ok", "synced": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Graph sync address failed: %s", e)
        raise HTTPException(status_code=500, detail="Graph sync failed")


@router.post("/graph/sync/block")
async def graph_sync_block(body: dict[str, Any]):
    """Trigger a sync of a block into Neo4j."""
    chain = GraphChain(body.get("chain", "ethereum"))
    block_number = body.get("block_number")
    if block_number is None:
        raise HTTPException(status_code=400, detail="block_number is required")
    try:
        result = await _graph_sync.sync_block(chain, int(block_number))
        return {"status": "ok", "synced": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Graph sync block failed: %s", e)
        raise HTTPException(status_code=500, detail="Graph sync failed")


@router.post("/graph/watch")
async def graph_add_watch(body: dict[str, str]):
    """Add an address to the watchdog for real-time monitoring."""
    address = body.get("address", "")
    chain = GraphChain(body.get("chain", "ethereum"))
    if not address:
        raise HTTPException(status_code=400, detail="address is required")
    _watchdog.add_watch(address, chain)
    return {"status": "watching", "address": address, "chain": chain.value}


@router.delete("/graph/watch/{address:path}")
async def graph_remove_watch(address: str):
    """Remove an address from the watchdog."""
    _watchdog.remove_watch(address)
    return {"status": "removed", "address": address}


@router.get("/graph/watches")
async def graph_list_watches():
    """List all watched addresses."""
    return {"watches": _watchdog.list_watches()}


# ── Phase 6: Alerting Engine ──────────────────────────────────────────────────

from app.blockchain.application.alerts import alert_service as _alert_service


@router.get("/alerts/v2")
async def list_alerts_v2(
    org_id: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
):
    """List alerts from the new alerting engine."""
    return {
        "alerts": _alert_service.list_alerts(org_id, severity, status, limit),
        "stats": _alert_service.stats(org_id),
    }


@router.post("/alerts/v2/{alert_id}/acknowledge")
async def acknowledge_alert_v2(alert_id: str, body: dict[str, str]):
    """Acknowledge an alert."""
    user_id = body.get("user_id", "")
    if not _alert_service.acknowledge_alert(alert_id, user_id):
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"acknowledged": True}


@router.post("/alerts/v2/{alert_id}/dismiss")
async def dismiss_alert_v2(alert_id: str):
    """Dismiss an alert."""
    if not _alert_service.dismiss_alert(alert_id):
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"dismissed": True}


@router.get("/alerts/v2/stats")
async def alert_stats_v2(org_id: str | None = Query(default=None)):
    """Get alert statistics."""
    return _alert_service.stats(org_id)


# ── Phase 7: Travel Rule / CARF Compliance ────────────────────────────────────

from app.blockchain.application.compliance import (
    travel_rule_service as _travel_rule,
    VASPRegistry as _VASPRegistry,
    register_default_vasps as _reg_vasps,
    ComplianceCaseStatus,
)


@router.get("/compliance/vasps")
async def list_vasps(status: str | None = Query(default=None), jurisdiction: str | None = Query(default=None)):
    """List registered VASPs."""
    return {"vasps": _VASPRegistry.list(status, jurisdiction)}


@router.get("/compliance/vasps/{vasp_id}")
async def get_vasp(vasp_id: str):
    """Get VASP details."""
    vasp = _VASPRegistry.get(vasp_id)
    if not vasp:
        raise HTTPException(status_code=404, detail="VASP not found")
    return vasp.to_dict()


@router.get("/compliance/detect/{address}")
async def detect_vasp(address: str):
    """Detect if an address belongs to a known VASP."""
    vasp = _VASPRegistry.find_by_address(address)
    if vasp:
        return {"is_vasp": True, "vasp": vasp.to_dict()}
    return {"is_vasp": False}


@router.get("/compliance/cases")
async def list_compliance_cases(status: str | None = Query(default=None), limit: int = Query(default=50, ge=1, le=200)):
    """List travel rule compliance cases."""
    return {"cases": _travel_rule.list_cases(status, limit)}


@router.get("/compliance/cases/{case_id}")
async def get_compliance_case(case_id: str):
    """Get a compliance case with messages."""
    case = _travel_rule.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.post("/compliance/cases/{case_id}/notes")
async def add_case_note(case_id: str, body: dict[str, str]):
    """Add a note to a compliance case."""
    note = body.get("note", "")
    user = body.get("user", "")
    if not _travel_rule.add_case_note(case_id, note, user):
        raise HTTPException(status_code=404, detail="Case not found")
    return {"added": True}


@router.put("/compliance/cases/{case_id}/status")
async def update_case_status(case_id: str, body: dict[str, str]):
    """Update compliance case status."""
    status_str = body.get("status", "")
    try:
        status = ComplianceCaseStatus(status_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status_str}")
    if not _travel_rule.update_case_status(case_id, status):
        raise HTTPException(status_code=404, detail="Case not found")
    return {"updated": True, "status": status.value}


@router.get("/compliance/messages")
async def list_travel_rule_messages(status: str | None = Query(default=None), limit: int = Query(default=50, ge=1, le=200)):
    """List travel rule messages."""
    return {"messages": _travel_rule.list_messages(status, limit)}


@router.post("/compliance/messages/{msg_id}/acknowledge")
async def acknowledge_travel_rule_message(msg_id: str):
    """Acknowledge a received travel rule message."""
    if not _travel_rule.acknowledge_message(msg_id):
        raise HTTPException(status_code=404, detail="Message not found")
    return {"acknowledged": True}


@router.post("/compliance/reports/generate")
async def generate_carf_report(body: dict[str, Any]):
    """Generate a CARF report for a VASP."""
    vasp_id = body.get("vasp_id", "")
    year = body.get("year")
    quarter = body.get("quarter")
    if not all([vasp_id, year, quarter]):
        raise HTTPException(status_code=400, detail="vasp_id, year, and quarter are required")
    report = _travel_rule.generate_carf_report(vasp_id, int(year), int(quarter))
    if not report:
        raise HTTPException(status_code=404, detail="VASP not found")
    return {"report": report.to_dict()}


@router.get("/compliance/reports")
async def list_carf_reports(vasp_id: str | None = Query(default=None)):
    """List CARF reports."""
    return {"reports": _travel_rule.list_reports(vasp_id)}


@router.post("/compliance/reports/{report_id}/filed")
async def confirm_report_filed(report_id: str):
    """Confirm a CARF report has been filed."""
    if not _travel_rule.confirm_report_filed(report_id):
        raise HTTPException(status_code=404, detail="Report not found")
    return {"filed": True}


@router.get("/compliance/stats")
async def compliance_stats():
    """Get compliance statistics."""
    return _travel_rule.stats()


# ── Phase 5: OpenSearch Search ────────────────────────────────────────────────

from app.blockchain.infrastructure.search.search_service import search_service as _search


@router.get("/search/health")
async def search_health():
    """Health check for OpenSearch."""
    return _search.health()


@router.get("/search/unified")
async def unified_search(
    q: str = Query(..., min_length=1, max_length=200),
    chain: str | None = Query(default=None),
    size: int = Query(default=20, ge=1, le=100),
):
    """Full-text search across addresses, transactions, and contracts."""
    results = _search.unified_search(q, chain, size)
    total = sum(len(v) for v in results.values())
    return {"results": results, "total": total}


@router.get("/search/addresses")
async def search_addresses(
    q: str = Query(..., min_length=1, max_length=200),
    chain: str | None = Query(default=None),
    size: int = Query(default=20, ge=1, le=100),
):
    """Search blockchain addresses."""
    results = _search.search_addresses(q, chain, size)
    return {"addresses": results, "total": len(results)}


@router.get("/search/transactions")
async def search_transactions(
    q: str = Query(..., min_length=1, max_length=200),
    chain: str | None = Query(default=None),
    size: int = Query(default=50, ge=1, le=200),
):
    """Search transactions by address."""
    results = _search.search_transactions(q, chain, size)
    return {"transactions": results, "total": len(results)}
