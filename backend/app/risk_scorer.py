"""
Rule-based risk scoring engine for AttackSec platform.

Converts scan findings into a deterministic 0-100 risk score.
No AI, no external API calls — pure Python logic.

Scoring weights (from Master Build Spec):
  Open SSH (22) exposed                          +15
  Open RDP (3389) exposed                        +20
  Open database port (3306/5432/6379/27017)      +25
  SSL certificate expired                        +35
  SSL certificate expiring in <30 days           +15
  Missing SPF record in DNS TXT                  +10
  Missing DMARC record                           +10
  Large subdomain footprint (>50 subdomains)     +10
  WHOIS privacy not enabled                      +5
  Security headers present (HSTS, CSP, etc.)     -10  (placeholder for future)

Clamped to 0-100. Labels: 0-25 Low, 26-50 Medium, 51-75 High, 76-100 Critical.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone


# --- Port risk definitions ---

OPEN_SSH_PORTS = {22}
OPEN_RDP_PORTS = {3389}
OPEN_DB_PORTS = {3306, 5432, 6379, 27017}

PORT_SCORES = {
    22: 15,      # SSH
    3389: 20,    # RDP
    3306: 25,    # MySQL
    5432: 25,    # PostgreSQL
    6379: 25,    # Redis
    27017: 25,   # MongoDB
}


def calculate_risk(scan_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate a deterministic risk score from scan results.

    Args:
        scan_results: The full scan result dict (as produced by ScanRunner).

    Returns:
        {
            "risk_score": int,          # 0-100
            "label": str,               # Low / Medium / High / Critical
            "findings": [               # list of individual findings
                {
                    "category": str,
                    "detail": str,
                    "points": int,      # positive = adds risk, negative = reduces
                }
            ]
        }
    """
    findings: List[Dict[str, Any]] = []
    total = 0

    # --- Port checks ---
    total += _score_ports(scan_results.get("ports", {}), findings)

    # --- SSL checks ---
    total += _score_ssl(scan_results.get("ssl_certificates", {}), findings)

    # --- DNS checks (SPF / DMARC) ---
    total += _score_dns(scan_results.get("dns_records", {}), findings)

    # --- Subdomain footprint ---
    total += _score_subdomain_footprint(scan_results.get("subdomains", []), findings)

    # --- WHOIS privacy ---
    total += _score_whois(scan_results.get("whois"), findings)

    # --- Security headers (scored from HTTP responses in tech scanner data) ---
    total += _score_security_headers(scan_results.get("technologies", {}), findings)

    # Clamp
    total = max(0, min(100, total))

    label = _label(total)

    return {
        "risk_score": total,
        "label": label,
        "findings": findings,
    }


# ---------------------------------------------------------------------------
# Internal scoring helpers
# ---------------------------------------------------------------------------

def _score_ports(
    ports_by_host: Dict[str, List[Dict[str, Any]]],
    findings: List[Dict[str, Any]],
) -> int:
    """Score open ports across all hosts."""
    points = 0
    for host, port_list in ports_by_host.items():
        for port_info in port_list:
            port_num = port_info.get("port", 0)
            if port_num in PORT_SCORES:
                pts = PORT_SCORES[port_num]
                points += pts
                service_name = _port_label(port_num)
                findings.append({
                    "category": "open_port",
                    "detail": f"{service_name} (port {port_num}) exposed on {host}",
                    "points": pts,
                })
    return points


def _score_ssl(
    certs_by_host: Dict[str, Any],
    findings: List[Dict[str, Any]],
) -> int:
    """Score SSL certificate issues."""
    points = 0
    now = datetime.now(timezone.utc)

    for host, cert in certs_by_host.items():
        if not cert:
            # No cert data at all — may mean connection refused or no HTTPS
            continue

        # Expired
        if not cert.get("is_valid", True):
            pts = 35
            points += pts
            findings.append({
                "category": "ssl_expired",
                "detail": f"SSL certificate expired on {host}",
                "points": pts,
            })
            continue

        # Expiry check
        days_left = cert.get("days_until_expiry")
        if days_left is not None and days_left < 30:
            pts = 15
            points += pts
            findings.append({
                "category": "ssl_expiring",
                "detail": f"SSL certificate on {host} expires in {days_left} days",
                "points": pts,
            })

    return points


def _score_dns(
    dns_by_host: Dict[str, Dict[str, Any]],
    findings: List[Dict[str, Any]],
) -> int:
    """
    Check for missing SPF and DMARC records.

    SPF is typically a TXT record containing 'v=spf1'.
    DMARC is a TXT record on _dmarc.<domain> containing 'v=DMARC1'.
    """
    points = 0

    # Collect all TXT records across all hosts
    all_txt: List[str] = []
    for host, records in dns_by_host.items():
        if isinstance(records, dict):
            for rec in records.get("TXT", []):
                val = rec.get("value", "") if isinstance(rec, dict) else str(rec)
                all_txt.append(val.lower())

    # SPF check
    has_spf = any("v=spf1" in t for t in all_txt)
    if not has_spf:
        pts = 10
        points += pts
        findings.append({
            "category": "missing_spf",
            "detail": "No SPF record found in DNS TXT records",
            "points": pts,
        })

    # DMARC check — look for _dmarc subdomain TXT or any TXT with v=DMARC1
    has_dmarc = any("v=dmarc1" in t for t in all_txt)
    if not has_dmarc:
        pts = 10
        points += pts
        findings.append({
            "category": "missing_dmarc",
            "detail": "No DMARC record found",
            "points": pts,
        })

    return points


def _score_subdomain_footprint(
    subdomains: List[str],
    findings: List[Dict[str, Any]],
) -> int:
    """Flag large subdomain footprints (>50)."""
    count = len(subdomains)
    if count > 50:
        pts = 10
        findings.append({
            "category": "large_subdomain_footprint",
            "detail": f"Unusually large subdomain footprint: {count} subdomains discovered",
            "points": pts,
        })
        return pts
    return 0


def _score_whois(
    whois_data: Optional[Dict[str, Any]],
    findings: List[Dict[str, Any]],
) -> int:
    """
    Check WHOIS privacy.

    If registrant name/org/country are all present and non-empty, the domain
    owner's identity is exposed (privacy not enabled).
    """
    if not whois_data:
        return 0

    name = (whois_data.get("registrant_name") or "").strip()
    org = (whois_data.get("registrant_org") or "").strip()
    country = (whois_data.get("registrant_country") or "").strip()

    # If all three are populated, privacy is likely NOT enabled
    if name and org and country:
        pts = 5
        findings.append({
            "category": "whois_privacy_disabled",
            "detail": f"WHOIS registrant info exposed: {name} / {org} / {country}",
            "points": pts,
        })
        return pts

    return 0


def _score_security_headers(
    technologies_by_host: Dict[str, Any],
    findings: List[Dict[str, Any]],
) -> int:
    """
    Score missing security headers based on detected technologies.
    Checks if HSTS, CSP, or X-Frame-Options are mentioned in tech data.
    Negative points = risk reduction for good headers.
    """
    points = 0
    for host, techs in technologies_by_host.items():
        if not techs:
            continue
        tech_names = []
        if isinstance(techs, list):
            tech_names = [t.get("name", "") if isinstance(t, dict) else str(t) for t in techs]
        elif isinstance(techs, dict):
            for category, items in techs.items():
                if isinstance(items, list):
                    tech_names.extend([i.get("name", "") if isinstance(i, dict) else str(i) for i in items])

        tech_text = " ".join(tech_names).lower()

        has_hsts = "hsts" in tech_text or "strict-transport-security" in tech_text
        has_csp = "csp" in tech_text or "content-security-policy" in tech_text
        has_xfo = "x-frame-options" in tech_text

        if has_hsts and has_csp:
            pts = -10
            points += pts
            findings.append({
                "category": "security_headers_present",
                "detail": f"Good security headers (HSTS + CSP) detected on {host}",
                "points": pts,
            })
        elif not has_hsts and not has_csp:
            pts = 5
            points += pts
            findings.append({
                "category": "missing_security_headers",
                "detail": f"Missing HSTS and CSP headers on {host}",
                "points": pts,
            })

    return points


def _label(score: int) -> str:
    """Map numeric score to risk label."""
    if score <= 25:
        return "Low"
    elif score <= 50:
        return "Medium"
    elif score <= 75:
        return "High"
    else:
        return "Critical"


def _port_label(port: int) -> str:
    """Human-readable service name for a port."""
    labels = {
        21: "FTP",
        22: "SSH",
        23: "Telnet",
        25: "SMTP",
        53: "DNS",
        80: "HTTP",
        110: "POP3",
        143: "IMAP",
        443: "HTTPS",
        445: "SMB",
        993: "IMAPS",
        995: "POP3S",
        1433: "MSSQL",
        1723: "PPTP",
        3306: "MySQL",
        3389: "RDP",
        5432: "PostgreSQL",
        5900: "VNC",
        6379: "Redis",
        8080: "HTTP-Alt",
        8443: "HTTPS-Alt",
        27017: "MongoDB",
    }
    return labels.get(port, f"Port {port}")
