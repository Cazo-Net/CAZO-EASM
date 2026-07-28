"""Immutable investigation audit trail.

Records all actions taken during a blockchain investigation with:
- Tamper-evident hash chain
- Timestamped entries
- Actor attribution
- Export capability
"""
from __future__ import annotations

import hashlib
import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AuditTrail:
    """Immutable audit trail for blockchain investigations."""

    def __init__(
        self,
        case_id: str,
        investigator: str,
        organization_id: str,
    ):
        self.case_id = case_id
        self.investigator = investigator
        self.organization_id = organization_id
        self.trail_id = secrets.token_urlsafe(32)
        self.created_at = datetime.now(timezone.utc)

        self._entries: List[Dict[str, Any]] = []
        self._previous_hash = "GENESIS"

        # Record trail creation
        self.record("trail_created", "Investigation audit trail created")

    def record(
        self,
        action: str,
        detail: str,
        *,
        actor: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record an audit entry. Returns the entry hash."""
        entry_hash = self._compute_hash(action, detail)

        entry = {
            "sequence": len(self._entries),
            "action": action,
            "detail": detail,
            "actor": actor or self.investigator,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hash": entry_hash,
            "previous_hash": self._previous_hash,
            "metadata": metadata or {},
        }

        self._entries.append(entry)
        self._previous_hash = entry_hash

        return entry_hash

    def record_transaction_accessed(
        self,
        chain: str,
        tx_hash: str,
        *,
        purpose: str = "investigation",
    ) -> str:
        """Record that a transaction was accessed for investigation."""
        return self.record(
            "transaction_accessed",
            f"Accessed transaction {tx_hash[:16]}... on {chain}",
            metadata={"chain": chain, "tx_hash": tx_hash, "purpose": purpose},
        )

    def record_address_flagged(
        self,
        address: str,
        chain: str,
        reason: str,
    ) -> str:
        """Record that an address was flagged."""
        return self.record(
            "address_flagged",
            f"Flagged address {address[:16]}... on {chain}: {reason}",
            metadata={"address": address, "chain": chain, "reason": reason},
        )

    def record_evidence_added(
        self,
        item_type: str,
        item_id: str,
        description: str,
    ) -> str:
        """Record that evidence was added to the package."""
        return self.record(
            "evidence_added",
            f"Added {item_type} evidence: {description}",
            metadata={"item_type": item_type, "item_id": item_id},
        )

    def record_compliance_check(
        self,
        tx_hash: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a Travel Rule compliance check."""
        return self.record(
            "compliance_check",
            f"Travel Rule check for {tx_hash[:16]}...: {status}",
            metadata={"tx_hash": tx_hash, "status": status, "details": details},
        )

    def record_export(
        self,
        format: str,
        filename: str,
    ) -> str:
        """Record that evidence was exported."""
        return self.record(
            "evidence_exported",
            f"Exported evidence as {format}: {filename}",
            metadata={"format": format, "filename": filename},
        )

    def record_comment(self, comment: str) -> str:
        """Record an investigator comment."""
        return self.record(
            "comment",
            comment,
        )

    def verify_integrity(self) -> Dict[str, Any]:
        """Verify the integrity of the audit trail hash chain."""
        is_valid = True
        broken_at = None
        previous_hash = "GENESIS"

        for i, entry in enumerate(self._entries):
            # Verify chain linkage
            if entry["previous_hash"] != previous_hash:
                is_valid = False
                broken_at = i
                break

            # Recompute hash using the previous_hash stored at entry time
            data = f"{entry['previous_hash']}:{entry['action']}:{entry['detail']}"
            expected_hash = hashlib.sha256(data.encode()).hexdigest()
            if entry["hash"] != expected_hash:
                is_valid = False
                broken_at = i
                break

            previous_hash = entry["hash"]

        return {
            "is_valid": is_valid,
            "entry_count": len(self._entries),
            "broken_at": broken_at,
            "trail_id": self.trail_id,
            "case_id": self.case_id,
        }

    def to_json(self) -> str:
        """Export audit trail as JSON."""
        trail = {
            "trail_id": self.trail_id,
            "case_id": self.case_id,
            "investigator": self.investigator,
            "organization_id": self.organization_id,
            "created_at": self.created_at.isoformat(),
            "entries": self._entries,
            "integrity": self.verify_integrity(),
        }
        return json.dumps(trail, indent=2, default=str)

    def to_dict(self) -> Dict[str, Any]:
        """Export audit trail as dict."""
        return {
            "trail_id": self.trail_id,
            "case_id": self.case_id,
            "investigator": self.investigator,
            "organization_id": self.organization_id,
            "created_at": self.created_at.isoformat(),
            "entries": self._entries,
            "integrity": self.verify_integrity(),
        }

    def _compute_hash(self, action: str, detail: str) -> str:
        """Compute SHA-256 hash for an entry."""
        data = f"{self._previous_hash}:{action}:{detail}"
        return hashlib.sha256(data.encode()).hexdigest()
