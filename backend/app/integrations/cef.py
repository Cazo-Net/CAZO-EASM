"""CEF (Common Event Format) formatter for SIEM integrations.

Converts CAZO findings into CEF-formatted strings compatible with:
- Splunk (via HEC)
- Elastic Security
- QRadar
- ArcSight
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# CEF severity mapping (CAZO → CEF)
SEVERITY_MAP = {
    "critical": 10,
    "high": 7,
    "medium": 4,
    "low": 2,
    "info": 0,
}

# CEF device fields
DEVICE_VENDOR = "CAZO"
DEVICE_PRODUCT = "EASM"
DEVICE_VERSION = "2.0"


def format_cef(
    event_type: str,
    name: str,
    severity: str,
    extensions: Optional[Dict[str, Any]] = None,
    *,
    timestamp: Optional[float] = None,
) -> str:
    """Format a single event as a CEF string.

    CEF Format:
    CEF:0|Vendor|Product|Version|SignatureID|Name|Severity|Extension

    Args:
        event_type: Signature ID (e.g., "scan.completed", "finding.critical")
        name: Event name
        severity: CAZO severity (critical, high, medium, low, info)
        extensions: Key-value pairs for CEF extension fields
        timestamp: Unix timestamp (default: now)

    Returns:
        CEF-formatted string
    """
    sev_num = SEVERITY_MAP.get(severity.lower(), 5)
    ts = timestamp or time.time()

    # Build extension string
    ext_parts = []
    if extensions:
        for key, value in extensions.items():
            # CEF extension format: key=value
            # Escape special characters
            escaped = str(value).replace("\\", "\\\\").replace("=", "\\=").replace("\n", "\\n")
            ext_parts.append(f"{key}={escaped}")

    ext_str = " ".join(ext_parts)

    return (
        f"CEF:0|{DEVICE_VENDOR}|{DEVICE_PRODUCT}|{DEVICE_VERSION}"
        f"|{event_type}|{name}|{sev_num}"
        f"|{ext_str}"
    )


def finding_to_cef(finding: Dict[str, Any], domain: str = "") -> str:
    """Convert a CAZO finding dict to CEF format."""
    severity = finding.get("severity", "info")
    category = finding.get("category", "unknown")
    description = finding.get("description", finding.get("detail", "Unknown finding"))

    extensions = {
        "cs1": domain,
        "cs1Label": "Domain",
        "cs2": category,
        "cs2Label": "FindingCategory",
        "cs3": finding.get("subcategory", ""),
        "cs3Label": "FindingSubcategory",
        "cs4": finding.get("url", finding.get("header", "")),
        "cs4Label": "AffectedResource",
        "dhost": domain,
        "msg": description[:500],
        "rt": datetime.now(timezone.utc).isoformat(),
    }

    # Add risk contribution if present
    if "risk_contribution" in finding:
        extensions["cs5"] = str(finding["risk_contribution"])
        extensions["cs5Label"] = "RiskContribution"

    event_type = f"finding.{severity}" if category in ("exposure", "cors_misconfiguration", "open_redirect", "subdomain_takeover", "ssrf_surface") else f"event.{category}"

    return format_cef(
        event_type=event_type,
        name=description[:100],
        severity=severity,
        extensions=extensions,
    )


def scan_completed_to_cef(scan_data: Dict[str, Any]) -> str:
    """Convert scan completion event to CEF format."""
    extensions = {
        "cs1": scan_data.get("domain", ""),
        "cs1Label": "Domain",
        "cs2": scan_data.get("scan_type", "full"),
        "cs2Label": "ScanType",
        "cn1": scan_data.get("subdomains_found", 0),
        "cn1Label": "SubdomainsFound",
        "cn2": scan_data.get("ports_found", 0),
        "cn2Label": "PortsFound",
        "cn3": scan_data.get("vulnerabilities_found", 0),
        "cn3Label": "VulnerabilitiesFound",
        "cn4": scan_data.get("risk_score", 0),
        "cn4Label": "RiskScore",
        "dhost": scan_data.get("domain", ""),
        "msg": f"Scan completed for {scan_data.get('domain', 'unknown')}",
        "rt": datetime.now(timezone.utc).isoformat(),
    }

    return format_cef(
        event_type="scan.completed",
        name=f"Scan completed: {scan_data.get('domain', 'unknown')}",
        severity="medium" if scan_data.get("vulnerabilities_found", 0) > 0 else "low",
        extensions=extensions,
    )


def risk_score_to_cef(risk_data: Dict[str, Any]) -> str:
    """Convert risk score change event to CEF format."""
    old_score = risk_data.get("old_score", 0)
    new_score = risk_data.get("new_score", 0)
    severity = "critical" if new_score >= 76 else ("high" if new_score >= 51 else ("medium" if new_score >= 26 else "low"))

    extensions = {
        "cs1": risk_data.get("domain", ""),
        "cs1Label": "Domain",
        "cn1": old_score,
        "cn1Label": "PreviousRiskScore",
        "cn2": new_score,
        "cn2Label": "NewRiskScore",
        "cn3": new_score - old_score,
        "cn3Label": "RiskScoreDelta",
        "dhost": risk_data.get("domain", ""),
        "msg": f"Risk score changed from {old_score} to {new_score}",
        "rt": datetime.now(timezone.utc).isoformat(),
    }

    return format_cef(
        event_type="risk.score_changed",
        name=f"Risk score changed: {old_score} → {new_score}",
        severity=severity,
        extensions=extensions,
    )
