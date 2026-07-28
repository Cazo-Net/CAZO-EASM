"""Supply Chain Risk Assessment Report.

Generates a structured report of third-party risks from graph intelligence data.
Can be called from API endpoints or as part of scan pipeline.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.scanners.v2.graph_intel import AttackSurfaceGraph, build_graph_from_scan

logger = logging.getLogger(__name__)


class SupplyChainReport:
    """Generate supply chain risk assessment reports."""

    REPORTS_DIR = "reports/supply_chain"

    def __init__(self):
        os.makedirs(self.REPORTS_DIR, exist_ok=True)

    def generate(
        self,
        scan_data: Dict[str, Any],
        domain: str,
        format: str = "json",
    ) -> Dict[str, Any]:
        """Generate supply chain report from scan data.

        Returns the report dict and saves to disk.
        """
        # Build graph from scan data
        graph = build_graph_from_scan(scan_data, domain)

        # Gather supply chain intelligence
        supply_chain_map = graph.get_supply_chain_map()
        critical_paths = graph.get_critical_supply_chain_paths()
        concentration_risk = graph.get_vendor_concentration_risk()

        # Build report
        report = {
            "report": {
                "type": "Supply Chain Risk Assessment",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "domain": domain,
                "format": format,
            },
            "executive_summary": self._build_executive_summary(
                supply_chain_map, critical_paths, concentration_risk
            ),
            "vendor_inventory": self._build_vendor_inventory(supply_chain_map),
            "data_flow_analysis": self._build_data_flow_analysis(supply_chain_map),
            "script_injection_surface": self._build_script_injection_analysis(supply_chain_map),
            "critical_paths": critical_paths[:10],
            "concentration_risk": concentration_risk,
            "risk_recommendations": self._generate_recommendations(
                supply_chain_map, critical_paths, concentration_risk
            ),
        }

        # Save to disk
        filename = f"{domain}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self.REPORTS_DIR, filename)
        with open(filepath, "w") as f:
            json.dump(report, f, indent=2, default=str)

        report["report"]["file_path"] = filepath
        return report

    def _build_executive_summary(
        self,
        supply_chain_map: Dict[str, Any],
        critical_paths: List[Dict[str, Any]],
        concentration_risk: Dict[str, Any],
    ) -> Dict[str, Any]:
        summary = supply_chain_map.get("summary", {})

        high_risk_vendors = summary.get("high_risk_vendors", [])
        data_flow_count = summary.get("data_flow_count", 0)
        script_count = summary.get("script_injection_count", 0)
        affected_domains = summary.get("unique_domains_affected", 0)

        # Overall risk level
        if high_risk_vendors or script_count > 5:
            risk_level = "high"
        elif data_flow_count > 3 or script_count > 2:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "total_vendors": summary.get("total_vendors", 0),
            "high_risk_vendor_count": len(high_risk_vendors),
            "high_risk_vendors": [v["name"] for v in high_risk_vendors],
            "data_flow_count": data_flow_count,
            "script_injection_count": script_count,
            "affected_domains": affected_domains,
            "critical_paths_count": len(critical_paths),
            "single_points_of_failure": concentration_risk.get("single_point_of_failure", []),
            "overall_risk_level": risk_level,
            "risk_score": self._calculate_overall_score(
                high_risk_vendors, data_flow_count, script_count, critical_paths
            ),
        }

    def _calculate_overall_score(
        self,
        high_risk_vendors: List[Dict],
        data_flows: int,
        script_injections: int,
        critical_paths: List[Dict],
    ) -> int:
        score = 0
        score += len(high_risk_vendors) * 15
        score += min(30, data_flows * 3)
        score += min(25, script_injections * 5)
        score += min(20, len(critical_paths) * 5)
        return min(100, score)

    def _build_vendor_inventory(self, supply_chain_map: Dict[str, Any]) -> List[Dict[str, Any]]:
        vendors = supply_chain_map.get("vendors", {})
        inventory = []
        for vendor_id, vdata in vendors.items():
            inventory.append({
                "name": vdata["name"],
                "risk_score": vdata["risk_score"],
                "category": vdata["properties"].get("category", "unknown"),
                "vendor_type": vdata["properties"].get("vendor_type", "unknown"),
                "risk_level": vdata["properties"].get("risk_level", "unknown"),
                "connected_domains": vdata["properties"].get("connected_domains", []),
                "technologies": vdata.get("technologies", []),
            })
        # Sort by risk
        inventory.sort(key=lambda x: x["risk_score"], reverse=True)
        return inventory

    def _build_data_flow_analysis(self, supply_chain_map: Dict[str, Any]) -> Dict[str, Any]:
        data_flows = supply_chain_map.get("data_flows", [])

        # Group by category
        by_category: Dict[str, List[Dict]] = {}
        for flow in data_flows:
            cat = flow.get("category", "unknown")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(flow)

        # Map of data types flowing to third parties
        data_types = {
            "Analytics": "User behavior data, page views, events",
            "session_recording": "Full session recordings, clicks, scrolls",
            "auto_capture": "Automatic event capture, DOM snapshots",
            "CRM": "Customer data, contact information",
            "Support": "Chat messages, user interactions",
            "Payment": "Payment tokens, transaction data (PCI scoped)",
            "Authentication": "Identity data, login credentials",
            "Email": "Email addresses, communication content",
            "Monitoring": "Error data, performance metrics, stack traces",
            "feature_flags": "Feature toggle state, user segments",
            "ab_testing": "Test variations, user assignments",
        }

        return {
            "total_flows": len(data_flows),
            "by_category": {
                cat: {
                    "count": len(flows),
                    "vendors": list({f["vendor"] for f in flows}),
                    "domains_affected": list({f["domain"] for f in flows}),
                    "data_type": data_types.get(cat, "Unknown data type"),
                }
                for cat, flows in by_category.items()
            },
            "unique_vendors": len({f["vendor"] for f in data_flows}),
            "unique_domains": len({f["domain"] for f in data_flows}),
        }

    def _build_script_injection_analysis(self, supply_chain_map: Dict[str, Any]) -> Dict[str, Any]:
        injections = supply_chain_map.get("script_injections", [])

        return {
            "total_injection_points": len(injections),
            "vendors": [
                {
                    "name": inj["vendor"],
                    "category": inj["category"],
                    "domains": [inj["domain"]],
                }
                for inj in injections
            ],
            "unique_vendors": len({i["vendor"] for i in injections}),
            "unique_domains": len({i["domain"] for i in injections}),
            "risk": "Third-party scripts can execute arbitrary JavaScript in the user's browser",
        }

    def _generate_recommendations(
        self,
        supply_chain_map: Dict[str, Any],
        critical_paths: List[Dict[str, Any]],
        concentration_risk: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        recommendations = []
        summary = supply_chain_map.get("summary", {})

        # High risk vendors
        high_risk = summary.get("high_risk_vendors", [])
        if high_risk:
            recommendations.append({
                "priority": "high",
                "category": "vendor_risk",
                "title": "Review High-Risk Third-Party Vendors",
                "detail": f"Found {len(high_risk)} high-risk vendors: {', '.join(v['name'] for v in high_risk)}. "
                          "Evaluate if these services are necessary and consider alternatives.",
                "action": "Audit vendor security posture, review data sharing agreements",
            })

        # Script injection
        script_count = summary.get("script_injection_count", 0)
        if script_count > 0:
            recommendations.append({
                "priority": "high",
                "category": "script_injection",
                "title": "Implement Content Security Policy",
                "detail": f"{script_count} third-party scripts inject code. "
                          "Without CSP, any compromised vendor can inject malicious code.",
                "action": "Deploy CSP headers with strict-dynamic, audit third-party scripts regularly",
            })

        # Data flow risk
        data_flow_count = summary.get("data_flow_count", 0)
        if data_flow_count > 5:
            recommendations.append({
                "priority": "medium",
                "category": "data_privacy",
                "title": "Review Data Sharing with Third Parties",
                "detail": f"{data_flow_count} data flows to third parties detected. "
                          "Ensure GDPR/CCPA compliance for all data sharing.",
                "action": "Create data flow inventory, update privacy policy, review DPAs",
            })

        # Concentration risk
        spof = concentration_risk.get("single_point_of_failure", [])
        if spof:
            recommendations.append({
                "priority": "medium",
                "category": "concentration",
                "title": "Reduce Vendor Concentration Risk",
                "detail": f"Single points of failure detected: {', '.join(spof)}. "
                          "If these vendors go down, multiple services are affected.",
                "action": "Evaluate alternative providers, implement fallback mechanisms",
            })

        # Critical paths
        if critical_paths:
            recommendations.append({
                "priority": "high",
                "category": "attack_path",
                "title": "Critical Supply Chain Attack Paths",
                "detail": f"{len(critical_paths)} critical paths from high-risk vendors to your domains. "
                          "A compromise of these vendors could lead to domain compromise.",
                "action": "Isolate high-risk vendor scripts, implement SRI hashes, monitor vendor security advisories",
            })

        return sorted(recommendations, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x["priority"], 3))


def generate_supply_chain_report(
    scan_data: Dict[str, Any],
    domain: str,
    format: str = "json",
) -> Dict[str, Any]:
    """Convenience function for generating supply chain reports."""
    report = SupplyChainReport()
    return report.generate(scan_data, domain, format)
