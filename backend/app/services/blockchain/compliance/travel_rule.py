"""FATF Travel Rule compliance checker.

Evaluates whether a blockchain transaction meets Travel Rule requirements:
- Identifies VASPs involved
- Checks if above jurisdiction threshold
- Validates originator/beneficiary information completeness
- Returns compliance status with missing fields
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.services.blockchain.compliance.travel_rule_model import (
    TravelRuleStatus,
    VASPClassification,
)
from app.services.blockchain.intel import check_ofac_sanctions
from app.services.blockchain.labels.curated import lookup_address

logger = logging.getLogger(__name__)

# FATF Travel Rule thresholds by jurisdiction (USD)
JURISDICTION_THRESHOLDS = {
    "US": 3000,
    "EU": 1000,
    "GB": 1000,
    "SG": 1500,
    "JP": 1000,
    "KR": 1000,
    "AU": 1000,
    "CA": 1000,
    "DEFAULT": 1000,
}

# Required fields for Travel Rule compliance
REQUIRED_FIELDS = [
    "originator_name",
    "originator_account",
    "beneficiary_name",
    "beneficiary_account",
]

# Extended required fields for higher thresholds
EXTENDED_REQUIRED_FIELDS = REQUIRED_FIELDS + [
    "originator_address",
    "originator_date_of_birth",
    "originator_vasp_name",
    "beneficiary_vasp_name",
]

# Known regulated VASPs (simplified — production would use LEI database)
KNOWN_VASPS: Dict[str, Dict[str, Any]] = {
    "binance": {"name": "Binance", "classification": VASPClassification.REGULATED, "lei": "3338"},
    "coinbase": {"name": "Coinbase", "classification": VASPClassification.REGULATED, "lei": "3339"},
    "kraken": {"name": "Kraken", "classification": VASPClassification.REGULATED, "lei": "3340"},
    "okx": {"name": "OKX", "classification": VASPClassification.REGULATED, "lei": "3341"},
    "bybit": {"name": "Bybit", "classification": VASPClassification.REGULATED, "lei": "3342"},
    "bitfinex": {"name": "Bitfinex", "classification": VASPClassification.REGULATED, "lei": "3343"},
    "kucoin": {"name": "KuCoin", "classification": VASPClassification.REGULATED, "lei": "3344"},
    "gate.io": {"name": "Gate.io", "classification": VASPClassification.REGULATED, "lei": "3345"},
    "crypto.com": {"name": "Crypto.com", "classification": VASPClassification.REGULATED, "lei": "3346"},
    "huobi": {"name": "HTX", "classification": VASPClassification.REGULATED, "lei": "3347"},
}

# Known mixer/sanctioned addresses
MIXER_INDICATORS = [
    "tornado cash",
    "tornado",
    "blender",
    "mixer",
    "sinbad",
    "chipmixer",
    "wasabi",
    "samourai",
]


async def check_travel_rule(
    chain: str,
    tx_hash: str,
    from_address: str,
    to_address: str,
    amount_usd: float,
    *,
    jurisdiction: str = "US",
    originator_info: Optional[Dict[str, Any]] = None,
    beneficiary_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Check Travel Rule compliance for a transaction.

    Returns compliance status, missing fields, and VASP identification.
    """
    # Get threshold for jurisdiction
    threshold = JURISDICTION_THRESHOLDS.get(jurisdiction.upper(), JURISDICTION_THRESHOLDS["DEFAULT"])

    # Check if below threshold
    below_threshold = amount_usd < threshold
    if below_threshold:
        return {
            "status": TravelRuleStatus.EXEMPT.value,
            "below_threshold": True,
            "threshold_usd": threshold,
            "amount_usd": amount_usd,
            "compliance_score": 100.0,
            "missing_fields": [],
            "originator_vasp": None,
            "beneficiary_vasp": None,
            "sanctions_flag": False,
        }

    # Identify VASPs
    originator_vasp = await _identify_vasp(from_address)
    beneficiary_vasp = await _identify_vasp(to_address)

    # Check sanctions
    sanctions = await check_ofac_sanctions(from_address)
    sanctions_flag = sanctions is not None and sanctions.get("is_sanctioned", False)

    # Check if either party is a mixer
    originator_mixer = _is_mixer(originator_vasp, from_address)
    beneficiary_mixer = _is_mixer(beneficiary_vasp, to_address)

    # Build compliance check
    originator = originator_info or {}
    beneficiary = beneficiary_info or {}

    # Determine required fields based on amount
    req_fields = EXTENDED_REQUIRED_FIELDS if amount_usd >= 10000 else REQUIRED_FIELDS

    # Check missing fields
    missing = []
    for field in req_fields:
        if field.startswith("originator_"):
            key = field.replace("originator_", "")
            if not originator.get(key):
                missing.append(field)
        elif field.startswith("beneficiary_"):
            key = field.replace("beneficiary_", "")
            if not beneficiary.get(key):
                missing.append(field)

    # Calculate compliance score
    total_fields = len(req_fields)
    filled_fields = total_fields - len(missing)
    compliance_score = (filled_fields / total_fields * 100) if total_fields > 0 else 0

    # Determine status
    if sanctions_flag:
        status = TravelRuleStatus.NON_COMPLIANT
        compliance_score = 0
    elif originator_mixer or beneficiary_mixer:
        status = TravelRuleStatus.NON_COMPLIANT
        compliance_score = max(0, compliance_score - 50)
    elif len(missing) == 0:
        status = TravelRuleStatus.COMPLIANT
    elif compliance_score >= 50:
        status = TravelRuleStatus.PENDING  # Partially compliant
    else:
        status = TravelRuleStatus.NON_COMPLIANT

    return {
        "status": status.value,
        "below_threshold": False,
        "threshold_usd": threshold,
        "amount_usd": amount_usd,
        "compliance_score": round(compliance_score, 1),
        "missing_fields": missing,
        "originator_vasp": {
            "name": originator_vasp.get("name") if originator_vasp else None,
            "classification": originator_vasp.get("classification", VASPClassification.UNKNOWN).value if originator_vasp else VASPClassification.UNKNOWN.value,
            "lei": originator_vasp.get("lei") if originator_vasp else None,
        },
        "beneficiary_vasp": {
            "name": beneficiary_vasp.get("name") if beneficiary_vasp else None,
            "classification": beneficiary_vasp.get("classification", VASPClassification.UNKNOWN).value if beneficiary_vasp else VASPClassification.UNKNOWN.value,
            "lei": beneficiary_vasp.get("lei") if beneficiary_vasp else None,
        },
        "sanctions_flag": sanctions_flag,
        "sanctions_details": sanctions if sanctions_flag else None,
        "mixer_risk": {
            "originator": originator_mixer,
            "beneficiary": beneficiary_mixer,
        },
        "jurisdiction": jurisdiction,
    }


async def _identify_vasp(address: str) -> Optional[Dict[str, Any]]:
    """Identify if an address belongs to a known VASP."""
    # Check curated labels
    label = lookup_address(address)
    if label:
        entity_name = label.entity_name.lower()
        for vasp_key, vasp_info in KNOWN_VASPS.items():
            if vasp_key in entity_name or entity_name in vasp_key:
                return vasp_info
        # Return as unknown VASP if labeled as exchange
        if "exchange" in label.category.value:
            return {
                "name": label.entity_name,
                "classification": VASPClassification.REGULATED,
                "lei": None,
            }

    return None


def _is_mixer(vasp_info: Optional[Dict[str, Any]], address: str) -> bool:
    """Check if an address/entity is a known mixer."""
    if not vasp_info:
        return False
    name = vasp_info.get("name", "").lower()
    return any(indicator in name for indicator in MIXER_INDICATORS)


async def batch_check_travel_rule(
    transactions: List[Dict[str, Any]],
    jurisdiction: str = "US",
) -> List[Dict[str, Any]]:
    """Check Travel Rule compliance for multiple transactions."""
    results = []
    for tx in transactions:
        result = await check_travel_rule(
            chain=tx.get("chain", "ethereum"),
            tx_hash=tx.get("tx_hash", ""),
            from_address=tx.get("from_address", ""),
            to_address=tx.get("to_address", ""),
            amount_usd=tx.get("amount_usd", 0),
            jurisdiction=jurisdiction,
            originator_info=tx.get("originator_info"),
            beneficiary_info=tx.get("beneficiary_info"),
        )
        results.append(result)
    return results
