"""Intelligent contextual risk scoring engine.

Replaces the simple rule-based scorer with a multi-dimensional risk model:

Risk = f(Exposure, Technology, Vulnerability, Business, History, Threat)

Each dimension is scored 0-100, then combined with configurable weights.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Risk dimension weights (must sum to 1.0)
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS = {
    "exposure": 0.25,
    "technology": 0.20,
    "vulnerability": 0.25,
    "business": 0.10,
    "history": 0.10,
    "threat": 0.10,
}

SEVERITY_LABELS = [
    (0, 25, "Low"),
    (26, 50, "Medium"),
    (51, 75, "High"),
    (76, 100, "Critical"),
]

# Port risk mapping (service → base risk contribution)
PORT_RISK = {
    21: 15, 22: 10, 23: 25, 25: 8, 53: 5, 80: 3, 110: 10,
    143: 10, 443: 2, 445: 20, 993: 5, 995: 5,
    1433: 25, 1723: 15, 3306: 25, 3389: 25,
    5432: 25, 5900: 20, 6379: 30, 8080: 5, 8443: 3, 27017: 30,
}

# Technology risk contributions by category
TECH_RISK = {
    "web_server": {"apache": 5, "nginx": 3, "iis": 8, "lighttpd": 6},
    "cms": {"wordpress": 15, "drupal": 12, "joomla": 14, "magento": 18},
    "language": {"php": 10, "python": 4, "java": 8, "node": 5, "ruby": 7},
    "framework": {"django": 3, "flask": 4, "express": 5, "laravel": 8, "spring": 6},
    "cdn": {"cloudflare": -5, "akamai": -5, "fastly": -4, "aws_cloudfront": -4},
    "waf": {"cloudflare_waf": -8, "aws_waf": -7, "akamai_waf": -7},
    "database": {"mysql": 15, "postgresql": 12, "redis": 20, "mongodb": 20, "elasticsearch": 18},
}

# Known vulnerable version patterns
VULNERABLE_PATTERNS = [
    {"tech": "nginx", "version_pattern": "1.1[0-6]\\.", "cve": "multiple", "severity": "high"},
    {"tech": "apache", "version_pattern": "2\\.4\\.[0-4][0-9]\\.", "cve": "multiple", "severity": "high"},
    {"tech": "openssl", "version_pattern": "1\\.0\\.", "cve": "multiple", "severity": "critical"},
    {"tech": "php", "version_pattern": "7\\.[0-3]\\.", "cve": "multiple", "severity": "high"},
]


class RiskScoringEngine:
    """Multi-dimensional risk scoring engine."""

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or DEFAULT_WEIGHTS.copy()
        # Normalize weights to sum to 1.0
        total_w = sum(self.weights.values())
        if total_w > 0:
            self.weights = {k: v / total_w for k, v in self.weights.items()}

    def calculate(
        self,
        scan_results: Dict[str, Any],
        asset_metadata: Optional[Dict[str, Any]] = None,
        historical_data: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Calculate comprehensive risk score.

        Args:
            scan_results: Aggregated scan pipeline output
            asset_metadata: Business context (owner, criticality, environment)
            historical_data: Previous scan results for trend analysis

        Returns:
            {
                "risk_score": 0-100,
                "severity": "Low|Medium|High|Critical",
                "dimensions": {dimension: {score, weight, findings}},
                "findings": [...],
                "recommendations": [...],
            }
        """
        dimensions: Dict[str, Dict[str, Any]] = {}
        all_findings: List[Dict[str, Any]] = []

        # Score each dimension
        exp_score, exp_findings = self._score_exposure(scan_results)
        dimensions["exposure"] = {"score": exp_score, "weight": self.weights["exposure"], "findings": exp_findings}
        all_findings.extend(exp_findings)

        tech_score, tech_findings = self._score_technology(scan_results)
        dimensions["technology"] = {"score": tech_score, "weight": self.weights["technology"], "findings": tech_findings}
        all_findings.extend(tech_findings)

        # Supply chain risk (added to technology dimension)
        sc_score, sc_findings = self._score_supply_chain(scan_results)
        if sc_findings:
            tech_score = min(100, tech_score + sc_score)
            dimensions["technology"]["score"] = tech_score
            dimensions["technology"]["findings"].extend(sc_findings)
            all_findings.extend(sc_findings)

        vuln_score, vuln_findings = self._score_vulnerability(scan_results)
        dimensions["vulnerability"] = {"score": vuln_score, "weight": self.weights["vulnerability"], "findings": vuln_findings}
        all_findings.extend(vuln_findings)

        biz_score, biz_findings = self._score_business(scan_results, asset_metadata)
        dimensions["business"] = {"score": biz_score, "weight": self.weights["business"], "findings": biz_findings}
        all_findings.extend(biz_findings)

        hist_score, hist_findings = self._score_history(scan_results, historical_data)
        dimensions["history"] = {"score": hist_score, "weight": self.weights["history"], "findings": hist_findings}
        all_findings.extend(hist_findings)

        threat_score, threat_findings = self._score_threat_intel(scan_results)
        dimensions["threat"] = {"score": threat_score, "weight": self.weights["threat"], "findings": threat_findings}
        all_findings.extend(threat_findings)

        # Weighted combination
        raw_score = sum(
            dim["score"] * dim["weight"]
            for dim in dimensions.values()
        )
        final_score = max(0, min(100, round(raw_score)))
        severity = self._severity(final_score)

        recommendations = self._generate_recommendations(dimensions, all_findings)

        return {
            "risk_score": final_score,
            "severity": severity,
            "dimensions": dimensions,
            "findings": all_findings,
            "recommendations": recommendations,
        }

    # --- Dimension scorers ---

    def _score_exposure(self, data: Dict[str, Any]) -> Tuple[int, List[Dict]]:
        score = 0
        findings = []

        # Open ports
        ports_data = data.get("ports", {})
        if isinstance(ports_data, dict):
            for host, port_list in ports_data.items():
                if isinstance(port_list, list):
                    for p in port_list:
                        port_num = p.get("port", 0) if isinstance(p, dict) else 0
                        risk = PORT_RISK.get(port_num, 0)
                        if risk > 0:
                            score += risk
                            findings.append({
                                "category": "exposure",
                                "subcategory": "open_port",
                                "detail": f"Port {port_num} ({_port_name(port_num)}) exposed on {host}",
                                "risk_contribution": risk,
                                "severity": "high" if risk >= 20 else "medium",
                            })

        # Subdomain footprint
        subdomains = data.get("subdomains", [])
        sub_count = len(subdomains) if isinstance(subdomains, list) else 0
        if sub_count > 100:
            pts = min(20, sub_count // 20)
            score += pts
            findings.append({
                "category": "exposure",
                "subcategory": "large_footprint",
                "detail": f"Large attack surface: {sub_count} subdomains",
                "risk_contribution": pts,
                "severity": "medium",
            })

        # DNS exposure
        dns_data = data.get("dns", {})
        if isinstance(dns_data, dict):
            for host, records in dns_data.items():
                if isinstance(records, dict):
                    # Wildcard DNS
                    if "A" in records:
                        for rec in records["A"]:
                            val = rec.get("value", "") if isinstance(rec, dict) else str(rec)
                            if val == "*":
                                score += 10
                                findings.append({
                                    "category": "exposure",
                                    "subcategory": "wildcard_dns",
                                    "detail": f"Wildcard DNS record on {host}",
                                    "risk_contribution": 10,
                                    "severity": "medium",
                                })

        # Exposure validation findings (from exposure-validation scanner)
        exposure_data = data.get("exposure_validation", {})
        if isinstance(exposure_data, dict):
            ev_findings = exposure_data.get("findings", [])
            if isinstance(ev_findings, list):
                for ef in ev_findings:
                    if not isinstance(ef, dict):
                        continue
                    cat = ef.get("category", "")
                    sev = ef.get("severity", "info")
                    desc = ef.get("description", "")

                    # Map severity to risk contribution
                    sev_risk = {"critical": 30, "high": 20, "medium": 10, "low": 5, "info": 1}
                    risk_pts = sev_risk.get(sev, 0)

                    subcategory = "exposure_finding"
                    if cat == "cors_misconfiguration":
                        subcategory = "cors_misconfiguration"
                        risk_pts = max(risk_pts, 20)  # CORS issues are serious
                    elif cat == "open_redirect":
                        subcategory = "open_redirect"
                        risk_pts = max(risk_pts, 15)
                    elif cat == "subdomain_takeover":
                        subcategory = "subdomain_takeover"
                        risk_pts = max(risk_pts, 25)
                    elif cat == "ssrf_surface":
                        subcategory = "ssrf_surface"
                        risk_pts = max(risk_pts, 15)
                    elif cat == "missing_security_header":
                        subcategory = "missing_security_header"
                    elif cat == "info_disclosure":
                        subcategory = "info_disclosure"
                    elif cat == "ssl_tls":
                        subcategory = "ssl_tls"
                    elif cat in ("environment_file", "config_file", "source_control", "backup_file"):
                        subcategory = "sensitive_file"
                        risk_pts = max(risk_pts, 15)
                    elif cat in ("debug_endpoint", "admin_panel", "api_exposure"):
                        subcategory = "exposed_endpoint"

                    if risk_pts > 0:
                        score += risk_pts
                        findings.append({
                            "category": "exposure",
                            "subcategory": subcategory,
                            "detail": desc[:200],
                            "risk_contribution": risk_pts,
                            "severity": sev,
                        })

        return min(100, score), findings

    def _score_technology(self, data: Dict[str, Any]) -> Tuple[int, List[Dict]]:
        score = 0
        findings = []

        tech_data = data.get("technologies", {})
        if not isinstance(tech_data, dict):
            return score, findings

        for host, techs in tech_data.items():
            tech_list = []
            if isinstance(techs, list):
                tech_list = techs
            elif isinstance(techs, dict):
                for cat_items in techs.values():
                    if isinstance(cat_items, list):
                        tech_list.extend(cat_items)

            for tech in tech_list:
                if not isinstance(tech, dict):
                    continue
                name = tech.get("name", "").lower()
                version = tech.get("version", "")

                # Check known risky technologies
                for cat, techs_map in TECH_RISK.items():
                    for tech_name, risk in techs_map.items():
                        if tech_name in name:
                            if risk > 0:
                                score += risk
                                findings.append({
                                    "category": "technology",
                                    "subcategory": "risky_tech",
                                    "detail": f"{name} on {host} (risk: +{risk})",
                                    "risk_contribution": risk,
                                    "severity": "high" if risk >= 15 else "medium",
                                })
                            elif risk < 0:
                                score += risk  # Negative = risk reduction
                                findings.append({
                                    "category": "technology",
                                    "subcategory": "protective_tech",
                                    "detail": f"{name} on {host} (reduces risk: {risk})",
                                    "risk_contribution": risk,
                                    "severity": "info",
                                })

                # Check for known vulnerable versions
                if version:
                    for pattern in VULNERABLE_PATTERNS:
                        import re
                        if pattern["tech"] in name and re.search(pattern["version_pattern"], version):
                            pts = 20 if pattern["severity"] == "critical" else 15
                            score += pts
                            findings.append({
                                "category": "technology",
                                "subcategory": "vulnerable_version",
                                "detail": f"{name} {version} on {host} — known vulnerabilities ({pattern['cve']})",
                                "risk_contribution": pts,
                                "severity": pattern["severity"],
                            })

        return min(100, score), findings

    # ── Supply Chain Risk ────────────────────────────────────────────────────

    # Third-party service risk profiles: service → {risk_level, category, description}
    THIRD_PARTY_RISKS: Dict[str, Dict[str, Any]] = {
        # Analytics — data collection risk
        "google_analytics": {"risk": "medium", "category": "data_collection", "desc": "Google Analytics collects user data"},
        "google_tag_manager": {"risk": "medium", "category": "data_collection", "desc": "GTM can load arbitrary scripts"},
        "hotjar": {"risk": "medium", "category": "session_recording", "desc": "Hotjar records user sessions"},
        "fullstory": {"risk": "high", "category": "session_recording", "desc": "FullStory records all user interactions"},
        "mixpanel": {"risk": "low", "category": "analytics", "desc": "Mixpanel event tracking"},
        "amplitude": {"risk": "low", "category": "analytics", "desc": "Amplitude analytics"},
        "segment": {"risk": "medium", "category": "data_collection", "desc": "Segment collects and routes user data"},
        "pendo": {"risk": "medium", "category": "product_analytics", "desc": "Pendo tracks user behavior"},
        "heap": {"risk": "medium", "category": "auto_capture", "desc": "Heap auto-captures all user interactions"},
        "logrocket": {"risk": "high", "category": "session_recording", "desc": "LogRocket records sessions and network"},
        "clarity": {"risk": "medium", "category": "session_recording", "desc": "Microsoft Clarity session recording"},

        # Support — chat widget = script injection
        "intercom": {"risk": "medium", "category": "chat_widget", "desc": "Intercom chat widget injects scripts"},
        "drift": {"risk": "medium", "category": "chat_widget", "desc": "Drift chat widget injects scripts"},
        "zendesk": {"risk": "low", "category": "support", "desc": "Zendesk support widget"},
        "crisp": {"risk": "medium", "category": "chat_widget", "desc": "Crisp chat widget"},
        "tawk_to": {"risk": "medium", "category": "chat_widget", "desc": "tawk.to chat widget"},
        "livechat": {"risk": "low", "category": "support", "desc": "LiveChat widget"},

        # Payment — PCI scope
        "stripe": {"risk": "low", "category": "payment", "desc": "Stripe payment processing (PCI compliant)"},
        "paypal": {"risk": "low", "category": "payment", "desc": "PayPal payment processing"},
        "braintree": {"risk": "low", "category": "payment", "desc": "Braintree payment processing"},

        # Auth — identity risk
        "auth0": {"risk": "low", "category": "authentication", "desc": "Auth0 identity provider"},
        "okta": {"risk": "low", "category": "authentication", "desc": "Okta identity provider"},
        "firebase_auth": {"risk": "medium", "category": "authentication", "desc": "Firebase Auth (Google dependency)"},

        # Monitoring — data exfiltration risk
        "sentry": {"risk": "low", "category": "error_tracking", "desc": "Sentry error tracking (sends stack traces)"},
        "datadog": {"risk": "medium", "category": "monitoring", "desc": "Datadog APM (collects performance data)"},
        "new_relic": {"risk": "medium", "category": "monitoring", "desc": "New Relic APM (collects performance data)"},
        "logrocket": {"risk": "high", "category": "session_recording", "desc": "LogRocket (records DOM + network)"},

        # Feature flags — code execution risk
        "launchdarkly": {"risk": "medium", "category": "feature_flags", "desc": "LaunchDarkly (can toggle features remotely)"},

        # A/B testing — script injection
        "optimizely": {"risk": "medium", "category": "ab_testing", "desc": "Optimizely (injects variation scripts)"},
        "vwo": {"risk": "medium", "category": "ab_testing", "desc": "VWO (injects variation scripts)"},
    }

    def _score_supply_chain(self, data: Dict[str, Any]) -> Tuple[int, List[Dict]]:
        """Score supply chain risk from third-party services detected by tech-intel."""
        score = 0
        findings = []

        # Get technology data from scan results
        tech_data = data.get("technologies", {})
        if not isinstance(tech_data, dict):
            # Try alternative keys
            tech_data = data.get("technology_intelligence", {})
            if isinstance(tech_data, dict):
                tech_data = tech_data.get("data", {}).get("technologies", [])
                if isinstance(tech_data, list):
                    # Convert list to dict format
                    tech_data = {"_all": tech_data}

        if not isinstance(tech_data, dict):
            return score, findings

        # Flatten all detected technologies
        all_techs: list[dict] = []
        for host, techs in tech_data.items():
            if isinstance(techs, list):
                all_techs.extend(techs)
            elif isinstance(techs, dict):
                for cat_items in techs.values():
                    if isinstance(cat_items, list):
                        all_techs.extend(cat_items)

        # Check each detected tech against supply chain risk profiles
        third_party_count = 0
        high_risk_vendors: list[str] = []
        data_collectors: list[str] = []
        script_injectors: list[str] = []

        for tech in all_techs:
            if not isinstance(tech, dict):
                continue
            name = tech.get("name", "").lower()
            vendor_type = tech.get("vendor_type", "")
            category = tech.get("category", "")

            # Only score third-party services and SaaS platforms
            if vendor_type not in ("third_party_service", "saas_platform"):
                continue

            third_party_count += 1
            risk_profile = self.THIRD_PARTY_RISKS.get(name)

            if risk_profile:
                risk_level = risk_profile["risk"]
                risk_category = risk_profile["category"]

                if risk_level == "high":
                    pts = 15
                    high_risk_vendors.append(name)
                elif risk_level == "medium":
                    pts = 8
                else:
                    pts = 3

                score += pts

                # Track specific risk categories
                if risk_category in ("data_collection", "session_recording", "auto_capture"):
                    data_collectors.append(name)
                if risk_category in ("chat_widget", "ab_testing", "feature_flags"):
                    script_injectors.append(name)

                findings.append({
                    "category": "supply_chain",
                    "subcategory": f"third_party_{risk_level}_risk",
                    "detail": f"{risk_profile['desc']} [{name}]",
                    "risk_contribution": pts,
                    "severity": "high" if risk_level == "high" else ("medium" if risk_level == "medium" else "low"),
                    "vendor": name,
                    "risk_category": risk_category,
                })

        # Summary findings
        if third_party_count > 10:
            pts = min(15, third_party_count - 10)
            score += pts
            findings.append({
                "category": "supply_chain",
                "subcategory": "vendor_sprawl",
                "detail": f"High third-party dependency count: {third_party_count} vendors detected",
                "risk_contribution": pts,
                "severity": "medium",
            })

        if data_collectors:
            pts = 10
            score += pts
            findings.append({
                "category": "supply_chain",
                "subcategory": "data_collection_exposure",
                "detail": f"User data flows to third parties: {', '.join(data_collectors[:5])}",
                "risk_contribution": pts,
                "severity": "medium",
            })

        if script_injectors:
            pts = 8
            score += pts
            findings.append({
                "category": "supply_chain",
                "subcategory": "script_injection_surface",
                "detail": f"Third-party scripts can inject code: {', '.join(script_injectors[:5])}",
                "risk_contribution": pts,
                "severity": "medium",
            })

        if high_risk_vendors:
            findings.append({
                "category": "supply_chain",
                "subcategory": "high_risk_vendors",
                "detail": f"High-risk third-party vendors detected: {', '.join(high_risk_vendors)}",
                "risk_contribution": 0,  # Already scored individually
                "severity": "high",
            })

        return min(100, score), findings

    def _score_vulnerability(self, data: Dict[str, Any]) -> Tuple[int, List[Dict]]:
        score = 0
        findings = []

        # Security findings
        sec_findings = data.get("security_findings", [])
        if isinstance(sec_findings, list):
            for f in sec_findings:
                if isinstance(f, dict):
                    severity = f.get("severity", "info").lower()
                    pts = {"critical": 30, "high": 20, "medium": 10, "low": 5}.get(severity, 2)
                    score += pts
                    findings.append({
                        "category": "vulnerability",
                        "subcategory": f.get("type", "finding"),
                        "detail": f.get("description", f.get("detail", str(f))),
                        "risk_contribution": pts,
                        "severity": severity,
                    })

        # CVE correlation
        cve_findings = data.get("cve_correlation", [])
        if isinstance(cve_findings, list):
            for cve in cve_findings:
                if isinstance(cve, dict):
                    sev = cve.get("severity", "medium").lower()
                    pts = {"critical": 25, "high": 18, "medium": 10, "low": 4}.get(sev, 2)
                    score += pts
                    findings.append({
                        "category": "vulnerability",
                        "subcategory": "cve",
                        "detail": f"{cve.get('cve_id', 'CVE-?')}: {cve.get('description', '')}",
                        "risk_contribution": pts,
                        "severity": sev,
                    })

        # SSL/TLS issues
        ssl_data = data.get("ssl_certificates", {})
        if isinstance(ssl_data, dict):
            for host, cert in ssl_data.items():
                if not cert or not isinstance(cert, dict):
                    continue
                grade = cert.get("grade", "").upper()
                if grade in ("D", "F"):
                    pts = 20
                    score += pts
                    findings.append({
                        "category": "vulnerability",
                        "subcategory": "weak_tls",
                        "detail": f"Weak TLS grade {grade} on {host}",
                        "risk_contribution": pts,
                        "severity": "high",
                    })
                if not cert.get("is_valid", True):
                    pts = 30
                    score += pts
                    findings.append({
                        "category": "vulnerability",
                        "subcategory": "expired_cert",
                        "detail": f"Expired certificate on {host}",
                        "risk_contribution": pts,
                        "severity": "critical",
                    })
                days = cert.get("days_until_expiry")
                if days is not None and days < 7:
                    pts = 15
                    score += pts
                    findings.append({
                        "category": "vulnerability",
                        "subcategory": "expiring_cert",
                        "detail": f"Certificate on {host} expires in {days} days",
                        "risk_contribution": pts,
                        "severity": "high",
                    })

        return min(100, score), findings

    def _score_business(
        self, data: Dict[str, Any], metadata: Optional[Dict[str, Any]]
    ) -> Tuple[int, List[Dict]]:
        score = 0
        findings = []

        if not metadata:
            return 5, [{"category": "business", "subcategory": "no_context",
                        "detail": "No business context available for risk assessment",
                        "risk_contribution": 5, "severity": "info"}]

        # Criticality
        criticality = metadata.get("criticality", "normal").lower()
        if criticality == "critical":
            score += 30
            findings.append({
                "category": "business", "subcategory": "critical_asset",
                "detail": "Asset marked as business-critical",
                "risk_contribution": 30, "severity": "high",
            })
        elif criticality == "high":
            score += 15
            findings.append({
                "category": "business", "subcategory": "high_value_asset",
                "detail": "Asset has high business value",
                "risk_contribution": 15, "severity": "medium",
            })

        # Public-facing
        if metadata.get("public_facing", True):
            score += 10

        # Environment
        env = metadata.get("environment", "production").lower()
        if env == "production":
            score += 10
        elif env == "staging":
            score += 5

        return min(100, score), findings

    def _score_history(
        self, data: Dict[str, Any], historical: Optional[List[Dict[str, Any]]]
    ) -> Tuple[int, List[Dict]]:
        score = 0
        findings = []

        if not historical or len(historical) < 2:
            return 5, [{"category": "history", "subcategory": "no_history",
                        "detail": "Limited historical data for trend analysis",
                        "risk_contribution": 5, "severity": "info"}]

        # Compare with previous scan
        prev = historical[-2] if len(historical) >= 2 else {}
        curr = historical[-1] if historical else {}

        # New subdomains
        prev_subs = set(prev.get("subdomains", []))
        curr_subs = set(curr.get("subdomains", []))
        new_subs = curr_subs - prev_subs
        if new_subs:
            pts = min(15, len(new_subs) * 2)
            score += pts
            findings.append({
                "category": "history", "subcategory": "new_assets",
                "detail": f"{len(new_subs)} new subdomains discovered since last scan",
                "risk_contribution": pts, "severity": "medium",
            })

        # Removed subdomains (potential decommission)
        removed = prev_subs - curr_subs
        if removed:
            findings.append({
                "category": "history", "subcategory": "removed_assets",
                "detail": f"{len(removed)} subdomains removed since last scan",
                "risk_contribution": 0, "severity": "info",
            })

        # New open ports
        prev_ports = set(str(p) for p in prev.get("open_ports", []))
        curr_ports = set(str(p) for p in curr.get("open_ports", []))
        new_ports = curr_ports - prev_ports
        if new_ports:
            pts = min(20, len(new_ports) * 5)
            score += pts
            findings.append({
                "category": "history", "subcategory": "new_ports",
                "detail": f"{len(new_ports)} new open ports since last scan",
                "risk_contribution": pts, "severity": "high",
            })

        return min(100, score), findings

    def _score_threat_intel(self, data: Dict[str, Any]) -> Tuple[int, List[Dict]]:
        score = 0
        findings = []

        # Check for known risky patterns
        ports_data = data.get("ports", {})
        if isinstance(ports_data, dict):
            for host, port_list in ports_data.items():
                if not isinstance(port_list, list):
                    continue
                open_ports = {p.get("port", 0) if isinstance(p, dict) else 0 for p in port_list}

                # Admin panels exposed
                if 3389 in open_ports or 5900 in open_ports:
                    score += 15
                    findings.append({
                        "category": "threat", "subcategory": "remote_access",
                        "detail": f"Remote access (RDP/VNC) exposed on {host}",
                        "risk_contribution": 15, "severity": "high",
                    })

                # Database ports exposed
                db_ports = {3306, 5432, 6379, 27017, 9200, 1433}
                exposed_db = open_ports & db_ports
                if exposed_db:
                    pts = len(exposed_db) * 10
                    score += pts
                    findings.append({
                        "category": "threat", "subcategory": "exposed_database",
                        "detail": f"Database ports {exposed_db} exposed on {host}",
                        "risk_contribution": pts, "severity": "critical",
                    })

        return min(100, score), findings

    # --- Helpers ---

    def _severity(self, score: int) -> str:
        for low, high, label in SEVERITY_LABELS:
            if low <= score <= high:
                return label
        return "Critical"

    def _generate_recommendations(
        self, dimensions: Dict[str, Any], findings: List[Dict]
    ) -> List[Dict[str, str]]:
        recs = []
        seen = set()

        for f in findings:
            sev = f.get("severity", "")
            cat = f.get("subcategory", "")
            if sev in ("critical", "high") and cat not in seen:
                seen.add(cat)
                if cat in ("expired_cert", "expiring_cert"):
                    recs.append({
                        "priority": "critical" if cat == "expired_cert" else "high",
                        "action": "Renew or replace TLS certificate immediately",
                        "detail": f["detail"],
                    })
                elif cat in ("exposed_database", "remote_access"):
                    recs.append({
                        "priority": "critical",
                        "action": "Restrict access to internal network only",
                        "detail": f["detail"],
                    })
                elif cat == "vulnerable_version":
                    recs.append({
                        "priority": "high",
                        "action": "Upgrade to latest stable version",
                        "detail": f["detail"],
                    })
                elif cat == "weak_tls":
                    recs.append({
                        "priority": "high",
                        "action": "Upgrade TLS configuration (disable old protocols/ciphers)",
                        "detail": f["detail"],
                    })
                elif cat == "risky_tech":
                    recs.append({
                        "priority": "medium",
                        "action": f"Review {f['detail'].split(' on ')[0]} configuration",
                        "detail": f["detail"],
                    })

        return sorted(recs, key=lambda r: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(r["priority"], 4))


def _port_name(port: int) -> str:
    names = {
        21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
        80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS", 445: "SMB",
        993: "IMAPS", 995: "POP3S", 1433: "MSSQL", 1723: "PPTP",
        3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL", 5900: "VNC",
        6379: "Redis", 8080: "HTTP-Alt", 8443: "HTTPS-Alt", 27017: "MongoDB",
    }
    return names.get(port, f"Port-{port}")


# Singleton
risk_engine = RiskScoringEngine()
