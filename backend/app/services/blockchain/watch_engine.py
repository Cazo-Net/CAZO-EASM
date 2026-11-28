"""Wallet monitoring engine.

An organization adds the wallets and contracts it cares about (treasury and
hot wallets, deployed contracts, addresses tied to an incident). On a
schedule, and whenever a user presses "Check now", each watch is compared
against live chain data:

* **New activity**: any transaction newer than the last one seen.
* **Sanctioned counterparty**: a new transaction to or from an address on the
  OFAC SDN list. On the first check the recent history is screened too, so
  existing exposure shows up straight away.
* **Address sanctioned**: the watched address itself appears on the list.

Alerts are stored per organization (``BlockchainAlert``), deduplicated by a
fingerprint, and high-severity ones also go out as in-app/email notifications
to the person who added the watch. If a data source is not configured or is
down, the watch records that status and raises no alerts: nothing is guessed.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.blockchain import BlockchainAlert, BlockchainWatch
from app.schemas.blockchain import Chain
from app.services.blockchain.providers.base import DataSourceUnavailable, registry

logger = logging.getLogger(__name__)

_EVM_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_BTC_RE = re.compile(r"^(?:[13][1-9A-HJ-NP-Za-km-z]{25,34}|bc1[02-9ac-hj-np-zAC-HJ-NP-Z]{11,71})$")
_TRON_RE = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")
_SOL_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")

EXPLORERS: dict[Chain, str] = {
    Chain.ETHEREUM: "https://etherscan.io",
    Chain.POLYGON: "https://polygonscan.com",
    Chain.BNB: "https://bscscan.com",
    Chain.ARBITRUM: "https://arbiscan.io",
    Chain.OPTIMISM: "https://optimistic.etherscan.io",
    Chain.BASE: "https://basescan.org",
    Chain.AVALANCHE: "https://snowtrace.io",
    Chain.BITCOIN: "https://mempool.space",
    Chain.TRON: "https://tronscan.org/#",
    Chain.SOLANA: "https://solscan.io",
}

TX_WINDOW = 25  # newest transactions examined per check


def normalize_address(address: str, chain: Chain) -> str:
    """Validate an address for its chain and return its canonical form."""
    address = (address or "").strip()
    if chain == Chain.BITCOIN:
        ok = bool(_BTC_RE.match(address))
        if ok and address.lower().startswith("bc1"):
            address = address.lower()
    elif chain == Chain.TRON:
        ok = bool(_TRON_RE.match(address))
    elif chain == Chain.SOLANA:
        ok = bool(_SOL_RE.match(address))
    else:
        ok = bool(_EVM_RE.match(address))
        address = address.lower()
    if not ok:
        raise ValueError(f"That is not a valid {chain.value} address.")
    return address


def tx_url(chain: Chain, tx_hash: str) -> str | None:
    base = EXPLORERS.get(chain)
    return f"{base}/tx/{tx_hash}" if base and tx_hash else None


def address_url(chain: Chain, address: str) -> str | None:
    base = EXPLORERS.get(chain)
    if not base:
        return None
    return f"{base}/{'account' if chain == Chain.SOLANA else 'address'}/{address}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _same(a: str | None, b: str | None, chain: Chain) -> bool:
    if not a or not b:
        return False
    if chain == Chain.TRON or chain == Chain.SOLANA:
        return a == b
    return a.lower() == b.lower()


def _add_alert(db: Session, watch: BlockchainWatch, *, alert_type: str, severity: str, title: str,
               message: str, fingerprint: str, tx_hash: str | None = None, counterparty: str | None = None,
               source: str | None = None, reference_url: str | None = None,
               data: dict[str, Any] | None = None) -> BlockchainAlert | None:
    exists = (db.query(BlockchainAlert.id)
              .filter(BlockchainAlert.organization_id == watch.organization_id,
                      BlockchainAlert.fingerprint == fingerprint)
              .first())
    if exists:
        return None
    alert = BlockchainAlert(
        organization_id=watch.organization_id, watch_id=watch.id, chain=watch.chain, address=watch.address,
        alert_type=alert_type, severity=severity, title=title[:300], message=message, tx_hash=tx_hash,
        counterparty=counterparty, source=source, reference_url=reference_url, data=data or {},
        fingerprint=fingerprint[:200],
    )
    db.add(alert)
    return alert


async def check_watch_async(db: Session, watch: BlockchainWatch, notify: bool = True) -> dict[str, Any]:
    """Check one watch against live data. Returns a short result summary."""
    from app.services.blockchain.sanctions import OFAC_REFERENCE_URL, SOURCE_NAME, check_address, screen_many

    chain = Chain(watch.chain)
    provider = registry.get(chain)
    first_check = watch.last_checked_at is None
    new_alerts: list[BlockchainAlert] = []
    label = watch.label or f"{watch.address[:10]}…"

    if provider is None:
        watch.last_status = {"result": "unsupported_chain", "message": f"No data source for {chain.value}."}
        watch.last_checked_at = _now()
        db.commit()
        return {"result": "unsupported_chain", "new_alerts": 0}

    # 1. Is the watched address itself on the sanctions list?
    if watch.alert_on_sanctions:
        screening = await check_address(watch.address, chain)
        if screening.get("is_sanctioned"):
            a = _add_alert(
                db, watch, alert_type="address_sanctioned", severity="critical",
                title=f"Watched address {label} is on the OFAC sanctions list",
                message=("This address appears on the U.S. Treasury OFAC SDN list. Dealing with it may "
                         "breach sanctions law. Check with your compliance team before any further transfers."),
                fingerprint=f"addr_sanctioned:{chain.value}:{watch.address}",
                source=SOURCE_NAME, reference_url=OFAC_REFERENCE_URL,
            )
            if a:
                new_alerts.append(a)

    # 2. New transactions since the last check.
    try:
        txs = await provider.get_transactions(watch.address, page=1, page_size=TX_WINDOW)
    except DataSourceUnavailable as exc:
        watch.last_status = {"result": exc.reason, "message": exc.message, "setting": exc.setting}
        watch.last_checked_at = _now()
        db.commit()
        if notify:
            _notify(db, watch, new_alerts)
        return {"result": exc.reason, "message": exc.message, "new_alerts": len(new_alerts)}

    txs = [t for t in txs if t.hash]
    if first_check:
        fresh: list = []
        screened = txs  # look at recent history once, for existing exposure
    else:
        fresh = []
        for t in txs:
            if watch.last_tx_hash and t.hash == watch.last_tx_hash:
                break
            fresh.append(t)
        screened = fresh

    if watch.alert_on_new_tx and fresh:
        outgoing = [t for t in fresh if _same(t.from_address, watch.address, chain)]
        newest = fresh[0]
        a = _add_alert(
            db, watch, alert_type="new_transaction",
            severity="medium" if outgoing else "info",
            title=(f"{len(fresh)}{'+' if len(fresh) == TX_WINDOW else ''} new transaction(s) on {label}"
                   + (f", {len(outgoing)} outgoing" if outgoing else "")),
            message=f"Newest: {newest.hash} on {chain.value}"
                    + (f" at {newest.timestamp.isoformat()}" if newest.timestamp else "") + ".",
            fingerprint=f"newtx:{watch.id}:{newest.hash}",
            tx_hash=newest.hash, source=f"{chain.value} chain data", reference_url=tx_url(chain, newest.hash),
            data={"tx_hashes": [t.hash for t in fresh[:TX_WINDOW]], "outgoing": len(outgoing)},
        )
        if a:
            new_alerts.append(a)

    if watch.alert_on_sanctions and screened:
        counterparties: dict[str, Any] = {}
        for t in screened:
            for cp in (t.from_address, t.to_address):
                if cp and not _same(cp, watch.address, chain):
                    counterparties.setdefault(cp, t)
        listed = await screen_many(list(counterparties), chain)
        for cp in listed:
            t = counterparties[cp]
            direction = "sent funds to" if _same(t.from_address, watch.address, chain) else "received funds from"
            a = _add_alert(
                db, watch, alert_type="sanctioned_counterparty", severity="critical",
                title=f"{label} {direction} an OFAC-sanctioned address",
                message=(f"Transaction {t.hash} involves {cp}, which is on the OFAC SDN list. "
                         "Review the transaction and involve your compliance team."),
                fingerprint=f"sanc_cp:{watch.id}:{cp.lower() if chain not in (Chain.TRON, Chain.SOLANA) else cp}",
                tx_hash=t.hash, counterparty=cp, source=SOURCE_NAME, reference_url=tx_url(chain, t.hash),
            )
            if a:
                new_alerts.append(a)

    if txs:
        watch.last_tx_hash = txs[0].hash
        if txs[0].timestamp:
            watch.last_activity_at = txs[0].timestamp
    watch.last_checked_at = _now()
    watch.last_status = {"result": "ok", "transactions_seen": len(txs), "new_transactions": len(fresh)}
    try:
        db.commit()
    except IntegrityError:
        # A concurrent check stored the same alert first; that is fine.
        db.rollback()
        return {"result": "ok", "new_alerts": 0}
    if notify:
        _notify(db, watch, new_alerts)
    return {"result": "ok", "new_alerts": len(new_alerts), "new_transactions": len(fresh)}


def _notify(db: Session, watch: BlockchainWatch, alerts: list[BlockchainAlert]) -> None:
    serious = [a for a in alerts if a.severity in ("critical", "high", "medium")]
    if not serious or not watch.created_by:
        return
    try:
        from app.services.notification_service import dispatch_notification

        worst = ("critical" if any(a.severity == "critical" for a in serious)
                 else "high" if any(a.severity == "high" for a in serious) else "medium")
        dispatch_notification(
            db=db, organization_id=watch.organization_id, user_id=watch.created_by,
            notification_type=f"new_finding_{worst}",
            title=serious[0].title if len(serious) == 1 else f"{len(serious)} blockchain alerts for {watch.label or watch.address}",
            message="; ".join(a.title for a in serious[:3]),
            related_entity_type="blockchain_watch", related_entity_id=watch.id,
            data={"watch_id": watch.id, "alert_ids": [a.id for a in serious[:20]]},
        )
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.warning("Could not send blockchain alert notification for watch %s", watch.id, exc_info=True)


def _run(coro):
    """Run a coroutine from sync code, even if this thread already has a loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def run_due_watches(db: Session, limit: int = 50) -> int:
    """Check every active watch whose interval has passed. Returns how many ran."""
    minutes = max(5, int(getattr(settings, "BLOCKCHAIN_WATCH_CHECK_MINUTES", 60) or 60))
    cutoff = _now() - timedelta(minutes=minutes)
    due = (db.query(BlockchainWatch)
           .filter(BlockchainWatch.is_active.is_(True))
           .filter((BlockchainWatch.last_checked_at.is_(None)) | (BlockchainWatch.last_checked_at < cutoff))
           .order_by(BlockchainWatch.last_checked_at)
           .limit(limit).all())
    ran = 0
    for w in due:
        try:
            _run(check_watch_async(db, w))
            ran += 1
        except Exception:  # noqa: BLE001
            db.rollback()
            logger.exception("Blockchain watch %s failed", w.id)
    return ran
