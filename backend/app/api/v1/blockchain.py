"""Blockchain Intelligence API routes.

Three kinds of routes live here:

* **Lookups** (``/wallet``, ``/transaction``, ``/contract``, ``/search`` ...):
  read public chain data for any address. They hold no customer data. When a
  chain's data source is not configured or is down they answer 503 with a
  ``data_source_*`` code; they never return made-up numbers.
* **Organization data** (``/watches``, ``/alerts``, ``/cases``): stored in
  the database with ``organization_id``. The organization and the acting
  user always come from the signed-in user, never from the request, and
  every query filters on them, so one customer cannot see or change another
  customer's data. Someone else's record answers 404, the same as a missing one.
* **Platform internals** (``/graph``, ``/alerts/v2``, ``/compliance``,
  ``/search/unified`` ...): shared, global stores (Neo4j, OpenSearch, the
  travel-rule engine) that have no per-organization separation. They are
  limited to platform superusers.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.permissions import Permission, require_any_permission
from app.database import get_db
from app.models.blockchain import (
    BlockchainAlert,
    BlockchainCase,
    BlockchainCaseEntry,
    BlockchainCaseMember,
    BlockchainWatch,
)
from app.models.user import User
from app.schemas.blockchain import (
    Chain,
    PaginatedResponse,
)
from app.services.blockchain.attribution import attribute_address
from app.services.blockchain.labels.curated import get_curated_labels
from app.services.blockchain.providers.base import DataSourceUnavailable, registry
from app.services.blockchain.risk import compute_risk

logger = logging.getLogger(__name__)

router = APIRouter()

_ETH_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_BTC_ADDRESS_RE = re.compile(r"^(1|3|bc1)[a-zA-HJ-NP-Z0-9]{25,62}$")

_DATA_SOURCES: dict[Chain, dict[str, Any]] = {
    Chain.BITCOIN: {"source": "Blockstream Esplora (public)", "setting": None},
    Chain.SOLANA: {"source": "Solana public RPC", "setting": None},
    Chain.TRON: {"source": "TronGrid", "setting": None},
}


def _source_unavailable(exc: DataSourceUnavailable) -> HTTPException:
    return HTTPException(status_code=503, detail=exc.to_detail())


def _provider(chain: Chain):
    provider = registry.get(chain)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Chain not supported: {chain.value}")
    return provider


def _writer():
    return require_any_permission(Permission.MANAGE_ASSETS, Permission.CREATE_SCAN)


def _org(user: User) -> str:
    if not user.organization_id:
        raise HTTPException(status_code=403, detail="Join or create an organization first.")
    return user.organization_id


def _platform_admin(user: User = Depends(get_current_user)) -> User:
    """Shared, cross-organization stores are for platform operators only."""
    if user.role != "superuser":
        raise HTTPException(status_code=403, detail="Platform administrator access required")
    return user


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _audit(db: Session, action: str, user: User, target_type: str, target_id: str, detail: dict) -> None:
    try:
        from app.services.audit import log_event
        log_event(db, action=action, organization_id=user.organization_id, actor_id=user.id,
                  target_type=target_type, target_id=target_id, detail=detail)
    except Exception:  # noqa: BLE001 - auditing must not block the request
        db.rollback()


# ── Lookups (public chain data) ──────────────────────────────────────────────

@router.get("/chains")
async def supported_chains():
    """Each chain with whether live data is connected, and what it needs if not."""
    chains = []
    for chain in registry.supported_chains:
        provider = registry.get(chain)
        info = _DATA_SOURCES.get(chain, {"source": "Etherscan V2 API", "setting": "ETHERSCAN_API_KEY"})
        live = bool(provider and provider.is_available())
        chains.append({
            "chain": chain.value,
            "live": live,
            "source": info["source"],
            "needs": None if live else info["setting"],
        })
    return {
        "chains": [c["chain"] for c in chains if c["live"]],
        "status": chains,
        "primary": "ethereum",
    }


@router.get("/wallet/{address}")
async def get_wallet(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    provider = _provider(chain)
    try:
        wallet = await provider.get_wallet_summary(address)
    except DataSourceUnavailable as e:
        raise _source_unavailable(e)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Wallet lookup failed: %s", e)
        raise HTTPException(status_code=502, detail="The chain data source returned an error. Try again shortly.")

    attribution, risk = await asyncio.gather(
        attribute_address(address, chain),
        compute_risk(address, chain),
        return_exceptions=True,
    )

    return {
        "wallet": wallet.model_dump(mode="json"),
        "attribution": attribution.model_dump(mode="json") if attribution and not isinstance(attribution, Exception) else None,
        "risk": risk.model_dump(mode="json") if risk and not isinstance(risk, Exception) else None,
        "data_source": _DATA_SOURCES.get(chain, {"source": "Etherscan V2 API"})["source"],
        # Kept for older clients. Live data only: simulated data was removed.
        "mock_mode": False,
    }


@router.get("/wallet/{address}/transactions")
async def get_transactions(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    provider = _provider(chain)
    try:
        txs = await provider.get_transactions(address, page, page_size)
        return PaginatedResponse(
            items=[tx.model_dump(mode="json") for tx in txs],
            total=len(txs) + (page - 1) * page_size,
            page=page,
            page_size=page_size,
            has_next=len(txs) == page_size,
        )
    except DataSourceUnavailable as e:
        raise _source_unavailable(e)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Transaction fetch failed: %s", e)
        raise HTTPException(status_code=502, detail="Failed to fetch transactions")


@router.get("/transaction/{tx_hash}")
async def get_transaction(
    tx_hash: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    provider = _provider(chain)
    try:
        tx = await provider.get_transaction(tx_hash)
        return tx.model_dump(mode="json")
    except DataSourceUnavailable as e:
        raise _source_unavailable(e)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Transaction fetch failed: %s", e)
        raise HTTPException(status_code=502, detail="Failed to fetch transaction")


@router.get("/contract/{address}")
async def get_contract(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    provider = _provider(chain)
    try:
        contract = await provider.get_contract_detail(address)
        if not contract:
            raise HTTPException(status_code=404, detail="Address is not a contract")
        return contract.model_dump(mode="json")
    except HTTPException:
        raise
    except DataSourceUnavailable as e:
        raise _source_unavailable(e)
    except Exception as e:
        logger.error("Contract fetch failed: %s", e)
        raise HTTPException(status_code=502, detail="Failed to fetch contract data")


@router.get("/wallet/{address}/tokens")
async def get_token_balances(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    provider = _provider(chain)
    try:
        tokens = await provider.get_token_balances(address)
        return {"tokens": [t.model_dump(mode="json") for t in tokens]}
    except DataSourceUnavailable as e:
        raise _source_unavailable(e)
    except Exception as e:
        logger.error("Token balance fetch failed: %s", e)
        raise HTTPException(status_code=502, detail="Failed to fetch token balances")


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
                results.append({"type": "address", "value": q, "chain": c.value,
                                "label": f"Ethereum address {q[:10]}..."})
            elif _BTC_ADDRESS_RE.match(q) and c == Chain.BITCOIN:
                results.append({"type": "address", "value": q, "chain": c.value,
                                "label": f"Bitcoin address {q[:12]}..."})

    return {"results": results, "total": len(results)}


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
    except DataSourceUnavailable as e:
        raise _source_unavailable(e)
    except Exception as e:
        logger.error("Clustering failed: %s", e)
        raise HTTPException(status_code=500, detail="Clustering analysis failed")


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
        return {
            "address": address,
            "is_known_bridge": is_bridge_address(address),
            "bridge_info": get_bridge_info(address),
            "interactions": await detect_bridge_interactions(address, chain),
        }
    except DataSourceUnavailable as e:
        raise _source_unavailable(e)
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
        return await get_bridge_volume(address, chain)
    except DataSourceUnavailable as e:
        raise _source_unavailable(e)
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


@router.get("/wallet/{address}/graph")
async def get_graph_analytics(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
    depth: int = Query(default=1, ge=1, le=3),
):
    """Get graph analytics for an address's transaction network."""
    from app.services.blockchain.graph.analytics import TransactionGraph
    provider = _provider(chain)
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
    except DataSourceUnavailable as e:
        raise _source_unavailable(e)
    except Exception as e:
        logger.error("Graph analytics failed: %s", e)
        raise HTTPException(status_code=500, detail="Graph analytics failed")


@router.get("/wallet/{address}/anomaly")
async def get_anomaly_score(
    address: str,
    chain: Chain = Chain.ETHEREUM,
):
    """ML anomaly score for a wallet. ``anomaly_score`` is null when no model is trained."""
    from app.services.blockchain.ml.anomaly import AnomalyScorer, _extract_features, explain_anomaly
    provider = _provider(chain)
    try:
        txs = await provider.get_transactions(address, page=1, page_size=100)
        tx_dicts = [tx.model_dump(mode="json") for tx in txs]
        features = _extract_features(address, tx_dicts)
        result = AnomalyScorer().score(features)
        if result.get("status") == "no_model":
            explanation = "No anomaly model has been trained yet, so no anomaly score is shown."
        else:
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
    except DataSourceUnavailable as e:
        raise _source_unavailable(e)
    except Exception as e:
        logger.error("Anomaly scoring failed: %s", e)
        raise HTTPException(status_code=500, detail="Anomaly scoring failed")


@router.get("/wallet/{address}/intel")
async def get_external_intel(
    address: str,
    chain: Chain = Query(default=Chain.ETHEREUM),
):
    """Sanctions screening (live OFAC SDN list, plus Chainalysis when keyed)."""
    from app.services.blockchain.intel import get_external_intel as _intel
    try:
        return await _intel(address, chain)
    except Exception as e:
        logger.error("External intel failed: %s", e)
        raise HTTPException(status_code=500, detail="External intel lookup failed")


@router.get("/wallet/{address}/sanctions")
async def check_sanctions(address: str, chain: Chain = Query(default=Chain.ETHEREUM)):
    """Check an address against the live OFAC SDN list.

    ``is_sanctioned`` is true, false, or null when the list could not be read
    (the address was not screened; that is not the same as "clean").
    """
    from app.services.blockchain.intel import check_ofac_sanctions
    try:
        result = await check_ofac_sanctions(address, chain)
        result["sanctioned"] = result.get("is_sanctioned")
        return result
    except Exception as e:
        logger.error("Sanctions check failed: %s", e)
        raise HTTPException(status_code=500, detail="Sanctions check failed")


@router.post("/copilot/ask")
async def copilot_ask(body: dict[str, Any]):
    """Ask the investigation copilot a natural language question."""
    from app.services.blockchain.copilot.copilot import ask_copilot
    from app.schemas.blockchain import CopilotQuery
    try:
        query = CopilotQuery(
            question=str(body.get("question", ""))[:2000],
            address=str(body.get("address", ""))[:200],
            chain=Chain(body.get("chain", "ethereum")),
        )
        response = await ask_copilot(query)
        return response.model_dump(mode="json")
    except DataSourceUnavailable as e:
        raise _source_unavailable(e)
    except ValueError:
        raise HTTPException(status_code=422, detail="Unknown chain")
    except Exception as e:
        logger.error("Copilot failed: %s", e)
        raise HTTPException(status_code=500, detail="Copilot query failed")


# ── Watches: wallets an organization monitors ────────────────────────────────

class WatchCreate(BaseModel):
    address: str = Field(min_length=10, max_length=128)
    chain: Chain = Chain.ETHEREUM
    label: Optional[str] = Field(default=None, max_length=200)
    alert_on_new_tx: bool = True
    alert_on_sanctions: bool = True


class WatchUpdate(BaseModel):
    label: Optional[str] = Field(default=None, max_length=200)
    alert_on_new_tx: Optional[bool] = None
    alert_on_sanctions: Optional[bool] = None
    is_active: Optional[bool] = None


def _watch_dict(w: BlockchainWatch, open_alerts: int = 0) -> dict:
    from app.services.blockchain.watch_engine import address_url
    return {
        "id": w.id,
        "chain": w.chain,
        "address": w.address,
        "label": w.label,
        "alert_on_new_tx": w.alert_on_new_tx,
        "alert_on_sanctions": w.alert_on_sanctions,
        "is_active": w.is_active,
        "created_at": _iso(w.created_at),
        "last_checked_at": _iso(w.last_checked_at),
        "last_activity_at": _iso(w.last_activity_at),
        "last_tx_hash": w.last_tx_hash,
        "last_status": w.last_status or {},
        "open_alerts": open_alerts,
        "explorer_url": address_url(Chain(w.chain), w.address),
    }


def _own_watch(db: Session, org_id: str, watch_id: str) -> BlockchainWatch:
    w = (db.query(BlockchainWatch)
         .filter(BlockchainWatch.id == watch_id, BlockchainWatch.organization_id == org_id)
         .first())
    if not w:
        raise HTTPException(status_code=404, detail="Watch not found")
    return w


@router.get("/watches")
async def list_watches(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    org_id = _org(user)
    watches = (db.query(BlockchainWatch)
               .filter(BlockchainWatch.organization_id == org_id)
               .order_by(BlockchainWatch.created_at.desc())
               .all())
    counts = dict(
        db.query(BlockchainAlert.watch_id, func.count(BlockchainAlert.id))
        .filter(BlockchainAlert.organization_id == org_id, BlockchainAlert.acknowledged.is_(False))
        .group_by(BlockchainAlert.watch_id)
        .all()
    )
    from app.config import settings
    return {
        "watches": [_watch_dict(w, counts.get(w.id, 0)) for w in watches],
        "total": len(watches),
        "limit": settings.BLOCKCHAIN_MAX_WATCHES_PER_ORG,
        "check_every_minutes": settings.BLOCKCHAIN_WATCH_CHECK_MINUTES,
    }


@router.post("/watches", status_code=201)
async def create_watch(body: WatchCreate, db: Session = Depends(get_db), user: User = Depends(_writer())):
    """Start monitoring a wallet or contract. The first check runs straight away."""
    from app.config import settings
    from app.services.blockchain.watch_engine import check_watch_async, normalize_address
    org_id = _org(user)
    try:
        address = normalize_address(body.address, body.chain)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if registry.get(body.chain) is None:
        raise HTTPException(status_code=400, detail=f"Chain not supported: {body.chain.value}")
    exists = (db.query(BlockchainWatch.id)
              .filter(BlockchainWatch.organization_id == org_id, BlockchainWatch.chain == body.chain.value,
                      BlockchainWatch.address == address)
              .first())
    if exists:
        raise HTTPException(status_code=409, detail="That address is already being watched.")
    limit = settings.BLOCKCHAIN_MAX_WATCHES_PER_ORG
    if db.query(BlockchainWatch).filter(BlockchainWatch.organization_id == org_id).count() >= limit:
        raise HTTPException(status_code=400, detail=f"You can watch at most {limit} addresses.")
    w = BlockchainWatch(
        organization_id=org_id, created_by=user.id, chain=body.chain.value, address=address,
        label=(body.label or "").strip() or None, alert_on_new_tx=body.alert_on_new_tx,
        alert_on_sanctions=body.alert_on_sanctions, last_status={},
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    _audit(db, "blockchain.watch.create", user, "blockchain_watch", w.id, {"chain": w.chain, "address": w.address})
    try:
        await check_watch_async(db, w, notify=False)
    except Exception:  # noqa: BLE001 - the scheduled check will retry
        db.rollback()
        logger.warning("First check of watch %s failed", w.id, exc_info=True)
    db.refresh(w)
    return _watch_dict(w)


@router.patch("/watches/{watch_id}")
async def update_watch(watch_id: str, body: WatchUpdate, db: Session = Depends(get_db),
                       user: User = Depends(_writer())):
    w = _own_watch(db, _org(user), watch_id)
    for field in ("alert_on_new_tx", "alert_on_sanctions", "is_active"):
        value = getattr(body, field)
        if value is not None:
            setattr(w, field, value)
    if body.label is not None:
        w.label = body.label.strip() or None
    db.commit()
    db.refresh(w)
    return _watch_dict(w)


@router.delete("/watches/{watch_id}", status_code=204)
async def delete_watch(watch_id: str, db: Session = Depends(get_db), user: User = Depends(_writer())):
    w = _own_watch(db, _org(user), watch_id)
    _audit(db, "blockchain.watch.delete", user, "blockchain_watch", w.id, {"chain": w.chain, "address": w.address})
    db.query(BlockchainAlert).filter(BlockchainAlert.watch_id == w.id).update(
        {BlockchainAlert.watch_id: None}, synchronize_session=False)
    db.delete(w)
    db.commit()
    return None


@router.post("/watches/{watch_id}/check")
async def check_watch_now(watch_id: str, db: Session = Depends(get_db), user: User = Depends(_writer())):
    """Check this watch against live chain data now."""
    from app.services.blockchain.watch_engine import check_watch_async
    w = _own_watch(db, _org(user), watch_id)
    result = await check_watch_async(db, w, notify=False)
    db.refresh(w)
    return {"watch": _watch_dict(w), **result}


# ── Alerts raised by the watch engine ────────────────────────────────────────

def _alert_dict(a: BlockchainAlert) -> dict:
    return {
        "id": a.id,
        "watch_id": a.watch_id,
        "chain": a.chain,
        "address": a.address,
        "alert_type": a.alert_type,
        "severity": a.severity,
        "title": a.title,
        "message": a.message,
        "tx_hash": a.tx_hash,
        "counterparty": a.counterparty,
        "source": a.source,
        "reference_url": a.reference_url,
        "acknowledged": a.acknowledged,
        "acknowledged_at": _iso(a.acknowledged_at),
        "created_at": _iso(a.created_at),
    }


_SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


@router.get("/alerts")
async def list_alerts(
    unacknowledged_only: bool = Query(default=False),
    watch_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    org_id = _org(user)
    q = db.query(BlockchainAlert).filter(BlockchainAlert.organization_id == org_id)
    if unacknowledged_only:
        q = q.filter(BlockchainAlert.acknowledged.is_(False))
    if watch_id:
        q = q.filter(BlockchainAlert.watch_id == watch_id)
    alerts = q.order_by(BlockchainAlert.created_at.desc()).limit(limit).all()
    return {"alerts": [_alert_dict(a) for a in alerts], "total": len(alerts)}


@router.get("/alerts/stats")
async def alert_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    org_id = _org(user)
    rows = (db.query(BlockchainAlert.severity, BlockchainAlert.acknowledged, func.count(BlockchainAlert.id))
            .filter(BlockchainAlert.organization_id == org_id)
            .group_by(BlockchainAlert.severity, BlockchainAlert.acknowledged)
            .all())
    stats = {"total": 0, "unacknowledged": 0, "critical": 0, "high": 0, "medium": 0, "info": 0}
    for severity, acked, n in rows:
        stats["total"] += n
        if not acked:
            stats["unacknowledged"] += n
        if severity in stats:
            stats[severity] += n
    return stats


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    a = (db.query(BlockchainAlert)
         .filter(BlockchainAlert.id == alert_id, BlockchainAlert.organization_id == _org(user))
         .first())
    if not a:
        raise HTTPException(status_code=404, detail="Alert not found")
    if not a.acknowledged:
        a.acknowledged = True
        a.acknowledged_by = user.id
        a.acknowledged_at = datetime.now(timezone.utc)
        db.commit()
    return {"acknowledged": True}


# ── Investigation cases ──────────────────────────────────────────────────────

CaseStatusLiteral = Literal["open", "in_review", "closed"]
CasePriorityLiteral = Literal["low", "medium", "high", "critical"]
MemberRoleLiteral = Literal["owner", "analyst", "viewer"]


class CaseAddress(BaseModel):
    chain: Chain = Chain.ETHEREUM
    address: str = Field(min_length=10, max_length=128)
    note: Optional[str] = Field(default=None, max_length=500)


class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=10000)
    priority: CasePriorityLiteral = "medium"
    assigned_to: Optional[str] = None
    addresses: list[CaseAddress] = Field(default_factory=list, max_length=100)


class CaseUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    description: Optional[str] = Field(default=None, max_length=10000)
    status: Optional[CaseStatusLiteral] = None
    priority: Optional[CasePriorityLiteral] = None
    assigned_to: Optional[str] = None
    addresses: Optional[list[CaseAddress]] = Field(default=None, max_length=100)


class NoteCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    entity_type: str = Field(default="address", max_length=30)
    entity_id: str = Field(default="", max_length=200)


class MemberAdd(BaseModel):
    user_id: str = Field(min_length=1, max_length=36)
    role: MemberRoleLiteral = "analyst"


def _case_dict(c: BlockchainCase) -> dict:
    return {
        "id": c.id,
        "org_id": c.organization_id,
        "title": c.title,
        "description": c.description or "",
        "status": c.status,
        "priority": c.priority,
        "created_by": c.created_by,
        "assigned_to": c.assigned_to,
        "addresses": c.addresses or [],
        "created_at": _iso(c.created_at),
        "updated_at": _iso(c.updated_at),
        "closed_at": _iso(c.closed_at),
    }


def _own_case(db: Session, user: User, case_id: str) -> BlockchainCase:
    c = (db.query(BlockchainCase)
         .filter(BlockchainCase.id == case_id, BlockchainCase.organization_id == _org(user))
         .first())
    if not c:
        raise HTTPException(status_code=404, detail="Case not found")
    return c


def _same_org_user(db: Session, org_id: str, user_id: Optional[str]) -> Optional[str]:
    """A case can only be assigned to, or shared with, people in the same organization."""
    if not user_id:
        return None
    found = db.query(User.id).filter(User.id == user_id, User.organization_id == org_id).first()
    if not found:
        raise HTTPException(status_code=422, detail="That user is not in your organization.")
    return user_id


def _clean_addresses(items: list[CaseAddress]) -> list[dict]:
    from app.services.blockchain.watch_engine import normalize_address
    out = []
    for item in items:
        try:
            addr = normalize_address(item.address, item.chain)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        out.append({"chain": item.chain.value, "address": addr, "note": item.note})
    return out


def _case_event(db: Session, case_id: str, user_id: str, action: str, detail: dict) -> None:
    db.add(BlockchainCaseEntry(case_id=case_id, kind="audit", user_id=user_id, action=action, detail=detail))


@router.post("/cases")
async def create_case(body: CaseCreate, db: Session = Depends(get_db), user: User = Depends(_writer())):
    org_id = _org(user)
    c = BlockchainCase(
        organization_id=org_id, title=body.title.strip(), description=body.description,
        priority=body.priority, created_by=user.id,
        assigned_to=_same_org_user(db, org_id, body.assigned_to),
        addresses=_clean_addresses(body.addresses), status="open",
    )
    db.add(c)
    db.flush()
    db.add(BlockchainCaseMember(case_id=c.id, user_id=user.id, role="owner", added_by=user.id))
    _case_event(db, c.id, user.id, "created", {"title": c.title})
    db.commit()
    db.refresh(c)
    _audit(db, "blockchain.case.create", user, "blockchain_case", c.id, {"title": c.title})
    return _case_dict(c)


@router.get("/cases")
async def list_cases(
    status: Optional[CaseStatusLiteral] = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(BlockchainCase).filter(BlockchainCase.organization_id == _org(user))
    if status:
        q = q.filter(BlockchainCase.status == status)
    cases = q.order_by(BlockchainCase.updated_at.desc()).all()
    return {"cases": [_case_dict(c) for c in cases]}


@router.get("/cases/stats")
async def case_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (db.query(BlockchainCase.status, func.count(BlockchainCase.id))
            .filter(BlockchainCase.organization_id == _org(user))
            .group_by(BlockchainCase.status).all())
    by_status = {s: n for s, n in rows}
    return {
        "total": sum(by_status.values()),
        "open": by_status.get("open", 0),
        "in_review": by_status.get("in_review", 0),
        "closed": by_status.get("closed", 0),
    }


@router.get("/cases/{case_id}")
async def get_case(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = _own_case(db, user, case_id)
    entries = (db.query(BlockchainCaseEntry).filter(BlockchainCaseEntry.case_id == c.id)
               .order_by(BlockchainCaseEntry.created_at).all())
    members = db.query(BlockchainCaseMember).filter(BlockchainCaseMember.case_id == c.id).all()
    return {
        "case": _case_dict(c),
        "annotations": [
            {"id": e.id, "user_id": e.user_id, "content": e.content, "entity_type": e.entity_type,
             "entity_id": e.entity_id, "created_at": _iso(e.created_at)}
            for e in entries if e.kind == "note"
        ],
        "members": [
            {"user_id": m.user_id, "role": m.role, "added_by": m.added_by, "added_at": _iso(m.added_at)}
            for m in members
        ],
        "audit": [
            {"user_id": e.user_id, "action": e.action, "detail": e.detail or {}, "created_at": _iso(e.created_at)}
            for e in entries if e.kind == "audit"
        ],
    }


@router.put("/cases/{case_id}")
async def update_case(case_id: str, body: CaseUpdate, db: Session = Depends(get_db),
                      user: User = Depends(_writer())):
    c = _own_case(db, user, case_id)
    changes: dict[str, Any] = {}
    if body.title is not None:
        c.title = body.title.strip()
        changes["title"] = c.title
    if body.description is not None:
        c.description = body.description
        changes["description"] = True
    if body.priority is not None:
        c.priority = body.priority
        changes["priority"] = body.priority
    if body.assigned_to is not None:
        c.assigned_to = _same_org_user(db, c.organization_id, body.assigned_to or None)
        changes["assigned_to"] = c.assigned_to
    if body.addresses is not None:
        c.addresses = _clean_addresses(body.addresses)
        changes["addresses"] = len(c.addresses)
    if body.status is not None and body.status != c.status:
        changes["status"] = {"from": c.status, "to": body.status}
        c.status = body.status
        c.closed_at = datetime.now(timezone.utc) if body.status == "closed" else None
    if changes:
        c.updated_at = datetime.now(timezone.utc)
        _case_event(db, c.id, user.id, "updated", changes)
    db.commit()
    db.refresh(c)
    return _case_dict(c)


@router.post("/cases/{case_id}/annotations")
async def add_annotation(case_id: str, body: NoteCreate, db: Session = Depends(get_db),
                         user: User = Depends(_writer())):
    c = _own_case(db, user, case_id)
    e = BlockchainCaseEntry(case_id=c.id, kind="note", user_id=user.id, content=body.content,
                            entity_type=body.entity_type, entity_id=body.entity_id)
    db.add(e)
    _case_event(db, c.id, user.id, "annotation_added", {"entity_type": body.entity_type, "entity_id": body.entity_id})
    c.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(e)
    return {"id": e.id, "case_id": c.id, "user_id": e.user_id, "content": e.content,
            "entity_type": e.entity_type, "entity_id": e.entity_id, "created_at": _iso(e.created_at)}


@router.post("/cases/{case_id}/members")
async def add_member(case_id: str, body: MemberAdd, db: Session = Depends(get_db),
                     user: User = Depends(_writer())):
    c = _own_case(db, user, case_id)
    member_id = _same_org_user(db, c.organization_id, body.user_id)
    existing = (db.query(BlockchainCaseMember)
                .filter(BlockchainCaseMember.case_id == c.id, BlockchainCaseMember.user_id == member_id).first())
    if existing:
        existing.role = body.role
        m = existing
    else:
        m = BlockchainCaseMember(case_id=c.id, user_id=member_id, role=body.role, added_by=user.id)
        db.add(m)
    _case_event(db, c.id, user.id, "member_added", {"user_id": member_id, "role": body.role})
    db.commit()
    return {"case_id": c.id, "user_id": m.user_id, "role": m.role}


@router.delete("/cases/{case_id}", status_code=204)
async def delete_case(case_id: str, db: Session = Depends(get_db), user: User = Depends(_writer())):
    c = _own_case(db, user, case_id)
    _audit(db, "blockchain.case.delete", user, "blockchain_case", c.id, {"title": c.title})
    db.query(BlockchainCaseEntry).filter(BlockchainCaseEntry.case_id == c.id).delete(synchronize_session=False)
    db.query(BlockchainCaseMember).filter(BlockchainCaseMember.case_id == c.id).delete(synchronize_session=False)
    db.delete(c)
    db.commit()
    return None


# ── Platform internals (superusers only) ─────────────────────────────────────
# These stores are global: they have no organization column, so showing them
# to customers would mix every customer's activity together.

_admin_only = [Depends(_platform_admin)]

from app.blockchain.application.graph_sync import graph_sync as _graph_sync  # noqa: E402
from app.blockchain.application.watchdog import watchdog as _watchdog  # noqa: E402
from app.blockchain.domain.value_objects.chain import Chain as GraphChain  # noqa: E402


@router.get("/graph/health", dependencies=_admin_only)
async def graph_health():
    """Health check for the Neo4j-backed graph layer."""
    return await _graph_sync.health()


@router.post("/graph/sync/address", dependencies=_admin_only)
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


@router.post("/graph/sync/block", dependencies=_admin_only)
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


@router.post("/graph/watch", dependencies=_admin_only)
async def graph_add_watch(body: dict[str, str]):
    """Add an address to the global graph watchdog."""
    address = body.get("address", "")
    chain = GraphChain(body.get("chain", "ethereum"))
    if not address:
        raise HTTPException(status_code=400, detail="address is required")
    _watchdog.add_watch(address, chain)
    return {"status": "watching", "address": address, "chain": chain.value}


@router.delete("/graph/watch/{address:path}", dependencies=_admin_only)
async def graph_remove_watch(address: str):
    _watchdog.remove_watch(address)
    return {"status": "removed", "address": address}


@router.get("/graph/watches", dependencies=_admin_only)
async def graph_list_watches():
    return {"watches": _watchdog.list_watches()}


from app.blockchain.application.alerts import alert_service as _alert_service  # noqa: E402


@router.get("/alerts/v2", dependencies=_admin_only)
async def list_alerts_v2(
    org_id: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
):
    """Alerts from the graph alerting engine (global)."""
    return {
        "alerts": _alert_service.list_alerts(org_id, severity, status, limit),
        "stats": _alert_service.stats(org_id),
    }


@router.post("/alerts/v2/{alert_id}/acknowledge", dependencies=_admin_only)
async def acknowledge_alert_v2(alert_id: str, user: User = Depends(_platform_admin)):
    if not _alert_service.acknowledge_alert(alert_id, user.id):
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"acknowledged": True}


@router.post("/alerts/v2/{alert_id}/dismiss", dependencies=_admin_only)
async def dismiss_alert_v2(alert_id: str):
    if not _alert_service.dismiss_alert(alert_id):
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"dismissed": True}


@router.get("/alerts/v2/stats", dependencies=_admin_only)
async def alert_stats_v2(org_id: str | None = Query(default=None)):
    return _alert_service.stats(org_id)


from app.blockchain.application.compliance import (  # noqa: E402
    travel_rule_service as _travel_rule,
    VASPRegistry as _VASPRegistry,
    ComplianceCaseStatus,
)


@router.get("/compliance/vasps", dependencies=_admin_only)
async def list_vasps(status: str | None = Query(default=None), jurisdiction: str | None = Query(default=None)):
    return {"vasps": _VASPRegistry.list(status, jurisdiction)}


@router.get("/compliance/vasps/{vasp_id}", dependencies=_admin_only)
async def get_vasp(vasp_id: str):
    vasp = _VASPRegistry.get(vasp_id)
    if not vasp:
        raise HTTPException(status_code=404, detail="VASP not found")
    return vasp.to_dict()


@router.get("/compliance/detect/{address}", dependencies=_admin_only)
async def detect_vasp(address: str):
    vasp = _VASPRegistry.find_by_address(address)
    if vasp:
        return {"is_vasp": True, "vasp": vasp.to_dict()}
    return {"is_vasp": False}


@router.get("/compliance/cases", dependencies=_admin_only)
async def list_compliance_cases(status: str | None = Query(default=None), limit: int = Query(default=50, ge=1, le=200)):
    return {"cases": _travel_rule.list_cases(status, limit)}


@router.get("/compliance/cases/{case_id}", dependencies=_admin_only)
async def get_compliance_case(case_id: str):
    case = _travel_rule.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.post("/compliance/cases/{case_id}/notes", dependencies=_admin_only)
async def add_case_note(case_id: str, body: dict[str, str], user: User = Depends(_platform_admin)):
    if not _travel_rule.add_case_note(case_id, body.get("note", ""), user.id):
        raise HTTPException(status_code=404, detail="Case not found")
    return {"added": True}


@router.put("/compliance/cases/{case_id}/status", dependencies=_admin_only)
async def update_case_status(case_id: str, body: dict[str, str]):
    status_str = body.get("status", "")
    try:
        status = ComplianceCaseStatus(status_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status_str}")
    if not _travel_rule.update_case_status(case_id, status):
        raise HTTPException(status_code=404, detail="Case not found")
    return {"updated": True, "status": status.value}


@router.get("/compliance/messages", dependencies=_admin_only)
async def list_travel_rule_messages(status: str | None = Query(default=None), limit: int = Query(default=50, ge=1, le=200)):
    return {"messages": _travel_rule.list_messages(status, limit)}


@router.post("/compliance/messages/{msg_id}/acknowledge", dependencies=_admin_only)
async def acknowledge_travel_rule_message(msg_id: str):
    if not _travel_rule.acknowledge_message(msg_id):
        raise HTTPException(status_code=404, detail="Message not found")
    return {"acknowledged": True}


@router.post("/compliance/reports/generate", dependencies=_admin_only)
async def generate_carf_report(body: dict[str, Any]):
    vasp_id = body.get("vasp_id", "")
    year = body.get("year")
    quarter = body.get("quarter")
    if not all([vasp_id, year, quarter]):
        raise HTTPException(status_code=400, detail="vasp_id, year, and quarter are required")
    report = _travel_rule.generate_carf_report(vasp_id, int(year), int(quarter))
    if not report:
        raise HTTPException(status_code=404, detail="VASP not found")
    return {"report": report.to_dict()}


@router.get("/compliance/reports", dependencies=_admin_only)
async def list_carf_reports(vasp_id: str | None = Query(default=None)):
    return {"reports": _travel_rule.list_reports(vasp_id)}


@router.post("/compliance/reports/{report_id}/filed", dependencies=_admin_only)
async def confirm_report_filed(report_id: str):
    if not _travel_rule.confirm_report_filed(report_id):
        raise HTTPException(status_code=404, detail="Report not found")
    return {"filed": True}


@router.get("/compliance/stats", dependencies=_admin_only)
async def compliance_stats():
    return _travel_rule.stats()


from app.blockchain.infrastructure.search.search_service import search_service as _search  # noqa: E402


@router.get("/search/health", dependencies=_admin_only)
async def search_health():
    return _search.health()


@router.get("/search/unified", dependencies=_admin_only)
async def unified_search(
    q: str = Query(..., min_length=1, max_length=200),
    chain: str | None = Query(default=None),
    size: int = Query(default=20, ge=1, le=100),
):
    """Full-text search across the shared OpenSearch index."""
    results = _search.unified_search(q, chain, size)
    total = sum(len(v) for v in results.values())
    return {"results": results, "total": total}


@router.get("/search/addresses", dependencies=_admin_only)
async def search_addresses(
    q: str = Query(..., min_length=1, max_length=200),
    chain: str | None = Query(default=None),
    size: int = Query(default=20, ge=1, le=100),
):
    results = _search.search_addresses(q, chain, size)
    return {"addresses": results, "total": len(results)}


@router.get("/search/transactions", dependencies=_admin_only)
async def search_transactions(
    q: str = Query(..., min_length=1, max_length=200),
    chain: str | None = Query(default=None),
    size: int = Query(default=50, ge=1, le=200),
):
    results = _search.search_transactions(q, chain, size)
    return {"transactions": results, "total": len(results)}
