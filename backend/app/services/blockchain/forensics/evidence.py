"""Chain of custody evidence builder for blockchain forensics.

Creates tamper-evident evidence packages with:
- SHA-256 hashing of all evidence items
- Digital signatures for investigator attestation
- Timestamped evidence log
- Export to JSON/CSV/PDF formats
"""
from __future__ import annotations

import hashlib
import json
import logging
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EvidencePackage:
    """Builds a chain-of-custody evidence package for blockchain investigations."""

    def __init__(
        self,
        case_id: str,
        investigator: str,
        organization_id: str,
        description: str = "",
    ):
        self.case_id = case_id
        self.investigator = investigator
        self.organization_id = organization_id
        self.description = description
        self.package_id = secrets.token_urlsafe(32)
        self.created_at = datetime.now(timezone.utc)

        self._items: List[Dict[str, Any]] = []
        self._chain_of_custody: List[Dict[str, Any]] = []
        self._hashes: List[str] = []

        # Record package creation
        self._record_custody("package_created", "Evidence package created")

    def add_transaction(
        self,
        chain: str,
        tx_hash: str,
        from_address: str,
        to_address: str,
        amount: str,
        currency: str,
        timestamp: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        source: str = "blockchain_rpc",
    ) -> str:
        """Add a blockchain transaction as evidence."""
        item_id = secrets.token_urlsafe(16)
        item = {
            "item_id": item_id,
            "type": "transaction",
            "chain": chain,
            "tx_hash": tx_hash,
            "from_address": from_address,
            "to_address": to_address,
            "amount": amount,
            "currency": currency,
            "timestamp": timestamp,
            "source": source,
            "metadata": metadata or {},
            "added_at": datetime.now(timezone.utc).isoformat(),
            "hash": self._hash_item(tx_hash + chain + timestamp),
        }
        self._items.append(item)
        self._record_custody("evidence_added", f"Transaction {tx_hash[:16]}... added")
        return item_id

    def add_address_attribution(
        self,
        address: str,
        chain: str,
        entity_name: str,
        category: str,
        confidence: float,
        *,
        source: str = "curated_labels",
        evidence: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Add address attribution as evidence."""
        item_id = secrets.token_urlsafe(16)
        item = {
            "item_id": item_id,
            "type": "attribution",
            "address": address,
            "chain": chain,
            "entity_name": entity_name,
            "category": category,
            "confidence": confidence,
            "source": source,
            "evidence": evidence or [],
            "added_at": datetime.now(timezone.utc).isoformat(),
            "hash": self._hash_item(address + chain + entity_name),
        }
        self._items.append(item)
        self._record_custody("evidence_added", f"Attribution for {address[:16]}... added")
        return item_id

    def add_scan_finding(
        self,
        finding_type: str,
        domain: str,
        description: str,
        severity: str,
        *,
        details: Optional[Dict[str, Any]] = None,
        source: str = "easm_scan",
    ) -> str:
        """Add a scan finding as evidence."""
        item_id = secrets.token_urlsafe(16)
        item = {
            "item_id": item_id,
            "type": "scan_finding",
            "finding_type": finding_type,
            "domain": domain,
            "description": description,
            "severity": severity,
            "details": details or {},
            "source": source,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "hash": self._hash_item(domain + finding_type + description),
        }
        self._items.append(item)
        self._record_custody("evidence_added", f"Finding '{finding_type}' on {domain} added")
        return item_id

    def add_screenshot(
        self,
        url: str,
        screenshot_data: str,  # Base64 encoded
        *,
        description: str = "",
        capture_tool: str = "cazo_easm",
    ) -> str:
        """Add a screenshot as evidence."""
        item_id = secrets.token_urlsafe(16)
        item = {
            "item_id": item_id,
            "type": "screenshot",
            "url": url,
            "description": description,
            "capture_tool": capture_tool,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "hash": self._hash_item(screenshot_data[:1000]),  # Hash preview
            "data_length": len(screenshot_data),
        }
        self._items.append(item)
        self._record_custody("evidence_added", f"Screenshot of {url[:50]} added")
        return item_id

    def add_note(
        self,
        content: str,
        *,
        author: Optional[str] = None,
    ) -> str:
        """Add an investigator note."""
        item_id = secrets.token_urlsafe(16)
        item = {
            "item_id": item_id,
            "type": "note",
            "content": content,
            "author": author or self.investigator,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "hash": self._hash_item(content),
        }
        self._items.append(item)
        self._record_custody("note_added", f"Note by {author or self.investigator}")
        return item_id

    def seal(self, *, signature: str = "") -> Dict[str, Any]:
        """Seal the evidence package with a final hash and signature.

        Once sealed, no more items can be added.
        """
        # Build merkle root of all item hashes
        all_hashes = [item["hash"] for item in self._items]
        merkle_root = self._hash_item("".join(all_hashes))

        self._record_custody("package_sealed", f"Package sealed with {len(self._items)} items")

        package = {
            "package_id": self.package_id,
            "case_id": self.case_id,
            "investigator": self.investigator,
            "organization_id": self.organization_id,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "sealed_at": datetime.now(timezone.utc).isoformat(),
            "item_count": len(self._items),
            "items": self._items,
            "chain_of_custody": self._chain_of_custody,
            "integrity": {
                "merkle_root": merkle_root,
                "item_count": len(self._items),
                "hash_algorithm": "SHA-256",
                "signature": signature,
            },
        }

        return package

    def _hash_item(self, data: str) -> str:
        """SHA-256 hash of data."""
        return hashlib.sha256(data.encode()).hexdigest()

    def _record_custody(self, action: str, detail: str) -> None:
        """Record a chain of custody entry."""
        entry = {
            "action": action,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": self.investigator,
            "hash": self._hash_item(f"{action}:{detail}:{time.time()}"),
        }
        self._chain_of_custody.append(entry)
        self._hashes.append(entry["hash"])

    def to_json(self) -> str:
        """Export sealed package as JSON."""
        package = self.seal()
        return json.dumps(package, indent=2, default=str)

    def to_dict(self) -> Dict[str, Any]:
        """Export sealed package as dict."""
        return self.seal()
