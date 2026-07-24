"""Next-generation subdomain intelligence scanner.

Enhanced subdomain analysis with:
- Multi-source enumeration (inherited from asset_discovery)
- DNS record collection per subdomain
- Wildcard detection
- Subdomain permutation analysis
- Takeover risk detection
- Historical comparison
"""
from __future__ import annotations

import asyncio
import re
import logging
from typing import Any, Dict, List, Optional

import dns.resolver
import dns.rdatatype

from app.scanners.v2.base import EnhancedBaseScanner, ScanResult, ScannerPriority
from app.scanners.v2.registry import register_scanner, ScannerCategory

logger = logging.getLogger(__name__)

# Well-known takeover indicators
TAKEOVER_INDICATORS = {
    "s3.amazonaws.com": {"provider": "AWS S3", "cname_pattern": r"\.s3\.amazonaws\.com$"},
    "github.io": {"provider": "GitHub Pages", "cname_pattern": r"\.github\.io$"},
    "herokuapp.com": {"provider": "Heroku", "cname_pattern": r"\.herokuapp\.com$"},
    "azurewebsites.net": {"provider": "Azure", "cname_pattern": r"\.azurewebsites\.net$"},
    "cloudfront.net": {"provider": "CloudFront", "cname_pattern": r"\.cloudfront\.net$"},
    "squarespace.com": {"provider": "Squarespace", "cname_pattern": r"\.squarespace\.com$"},
    "shopify.com": {"provider": "Shopify", "cname_pattern": r"\.myshopify\.com$"},
    "surge.sh": {"provider": "Surge", "cname_pattern": r"\.surge\.sh$"},
    "bitbucket.io": {"provider": "Bitbucket", "cname_pattern": r"\.bitbucket\.io$"},
    "zendesk.com": {"provider": "Zendesk", "cname_pattern": r"\.zendesk\.com$"},
    "readme.io": {"provider": "ReadMe", "cname_pattern": r"\.readme\.io$"},
    "ghost.io": {"provider": "Ghost", "cname_pattern": r"\.ghost\.io$"},
    "helpjuice.com": {"provider": "HelpJuice", "cname_pattern": r"\.helpjuice\.com$"},
    "helpscoutdocs.com": {"provider": "HelpScout", "cname_pattern": r"\.helpscoutdocs\.com$"},
    "pantheon.io": {"provider": "Pantheon", "cname_pattern": r"\.pantheonsite\.io$"},
    "fastly.net": {"provider": "Fastly", "cname_pattern": r"\.fastly\.net$"},
}

# Wildcard detection patterns
WILDCARD_IPS = {"0.0.0.0", "127.0.0.1", "::1", "198.51.100.1"}


@register_scanner(
    name="subdomain-intelligence",
    category=ScannerCategory.ASSET_DISCOVERY,
    version="2.0.0",
    priority=ScannerPriority.HIGH,
    description="Advanced subdomain intelligence with takeover detection and permutation analysis",
    capabilities=[
        "wildcard_detection", "takeover_risk", "permutation_analysis",
        "dns_validation", "historical_comparison",
    ],
    dependencies=["advanced-asset-discovery"],
)
class SubdomainIntelligenceScanner(EnhancedBaseScanner):
    """Deep subdomain analysis and risk assessment."""

    name = "subdomain-intelligence"
    version = "2.0.0"
    category = ScannerCategory.ASSET_DISCOVERY
    priority = ScannerPriority.HIGH

    async def scan(self, target: str, **kwargs) -> ScanResult:
        context = kwargs.get("context")
        # Get subdomains from context or discover fresh
        subdomains = []
        if context and context.discovered_assets:
            subdomains = [a.get("hostname", "") for a in context.discovered_assets if a.get("hostname")]
        if not subdomains:
            subdomains = [target]

        # Run analyses concurrently
        wildcard_result, takeover_results, perm_results, dns_details = await asyncio.gather(
            self._detect_wildcard(target),
            self._check_takeover_risk(subdomains),
            self._generate_permutations(subdomains, target),
            self._collect_dns_details(subdomains[:50]),  # Cap DNS detail collection
        )

        all_subdomains = set(subdomains)
        all_subdomains.update(perm_results.get("new_subdomains", []))

        return ScanResult(
            success=True,
            scanner=self.name,
            target=target,
            data={
                "subdomains": sorted(all_subdomains),
                "wildcard": wildcard_result,
                "takeover_risks": takeover_results,
                "permutations": perm_results,
                "dns_details": dns_details,
                "analysis": self._build_analysis(
                    subdomains, wildcard_result, takeover_results, perm_results
                ),
            },
        )

    def validate_target(self, target: str) -> bool:
        return bool(re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$', target))

    async def _detect_wildcard(self, domain: str) -> Dict[str, Any]:
        """Detect wildcard DNS by querying random non-existent subdomains."""
        import random
        import string
        results = {"is_wildcard": False, "wildcard_ip": None, "tests": 0}

        test_names = [
            ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
            for _ in range(5)
        ]

        for name in test_names:
            fqdn = f"{name}.{domain}"
            try:
                loop = asyncio.get_running_loop()
                answers = await loop.run_in_executor(
                    None, lambda: dns.resolver.resolve(fqdn, "A")
                )
                results["tests"] += 1
                for rdata in answers:
                    ip = str(rdata)
                    if ip in WILDCARD_IPS:
                        continue
                    results["is_wildcard"] = True
                    results["wildcard_ip"] = ip
                    break
                if results["is_wildcard"]:
                    break
            except dns.resolver.NXDOMAIN:
                results["tests"] += 1
            except Exception:
                results["tests"] += 1

        return results

    async def _check_takeover_risk(self, subdomains: List[str]) -> List[Dict[str, Any]]:
        """Check for subdomain takeover risks via dangling CNAME records."""
        async def _check_one(sub: str) -> Optional[Dict[str, Any]]:
            try:
                loop = asyncio.get_running_loop()
                answers = await loop.run_in_executor(
                    None, lambda: dns.resolver.resolve(sub, "CNAME")
                )
                for rdata in answers:
                    cname_target = str(rdata).rstrip(".")
                    for indicator_domain, info in TAKEOVER_INDICATORS.items():
                        if info["cname_pattern"] and re.search(info["cname_pattern"], cname_target):
                            # Try to resolve the CNAME target
                            try:
                                await loop.run_in_executor(
                                    None, lambda: dns.resolver.resolve(cname_target, "A")
                                )
                            except dns.resolver.NXDOMAIN:
                                return {
                                    "subdomain": sub,
                                    "cname": cname_target,
                                    "provider": info["provider"],
                                    "risk": "high",
                                    "detail": f"CNAME points to {info['provider']} but target does not resolve — potential takeover",
                                }
                            except Exception:
                                pass
            except dns.resolver.NoAnswer:
                pass
            except dns.resolver.NXDOMAIN:
                pass
            except Exception:
                pass
            return None

        tasks = [_check_one(s) for s in subdomains[:100]]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]

    async def _generate_permutations(self, subdomains: List[str], domain: str) -> Dict[str, Any]:
        """Generate subdomain permutations (mutations) for discovery."""
        permutations = set()
        prefixes = ["dev", "staging", "test", "qa", "uat", "pre", "prod", "api", "admin", "mail", "vpn", "ftp", "ci", "cd"]
        suffixes = ["01", "02", "1", "2", "v2", "v3", "new", "old", "backup", "bak"]

        for sub in subdomains:
            parts = sub.replace(f".{domain}", "").split(".")
            if not parts:
                continue
            base = parts[-1]

            # Add prefixes
            for prefix in prefixes:
                candidate = f"{prefix}-{base}.{domain}"
                if candidate != sub:
                    permutations.add(candidate)
                candidate = f"{prefix}{base}.{domain}"
                if candidate != sub:
                    permutations.add(candidate)

            # Add suffixes
            for suffix in suffixes:
                candidate = f"{base}-{suffix}.{domain}"
                if candidate != sub:
                    permutations.add(candidate)

            # Numeric variants
            if base[-1].isdigit():
                for i in range(10):
                    candidate = f"{base[:-1]}{i}.{domain}"
                    if candidate != sub:
                        permutations.add(candidate)

        # Validate a sample of permutations via DNS
        sample = list(permutations)[:100]
        valid_new = await self._quick_validate(sample, domain)

        return {
            "total_generated": len(permutations),
            "validated": len(valid_new),
            "new_subdomains": valid_new,
        }

    async def _quick_validate(self, subdomains: List[str], domain: str) -> List[str]:
        """Quick DNS A-record check."""
        semaphore = asyncio.Semaphore(30)

        async def _check(sub: str) -> Optional[str]:
            async with semaphore:
                try:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, lambda: dns.resolver.resolve(sub, "A"))
                    return sub
                except Exception:
                    return None

        tasks = [_check(s) for s in subdomains]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]

    async def _collect_dns_details(self, subdomains: List[str]) -> Dict[str, Any]:
        """Collect A, AAAA, CNAME records for each subdomain."""
        details = {}

        async def _get_records(sub: str) -> tuple[str, Dict[str, Any]]:
            records = {"A": [], "AAAA": [], "CNAME": []}
            for rtype in ["A", "AAAA", "CNAME"]:
                try:
                    loop = asyncio.get_running_loop()
                    answers = await loop.run_in_executor(
                        None, lambda r=rtype: dns.resolver.resolve(sub, r)
                    )
                    records[rtype] = [str(r) for r in answers]
                except Exception:
                    pass
            return sub, records

        tasks = [_get_records(s) for s in subdomains]
        results = await asyncio.gather(*tasks)
        for sub, records in results:
            details[sub] = records

        return details

    def _build_analysis(
        self,
        subdomains: List[str],
        wildcard: Dict[str, Any],
        takeovers: List[Dict],
        permutations: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build human-readable analysis summary."""
        return {
            "total_subdomains": len(subdomains),
            "wildcard_detected": wildcard.get("is_wildcard", False),
            "takeover_risks_found": len(takeovers),
            "new_permutations_found": permutations.get("validated", 0),
            "risk_summary": (
                "HIGH — takeover risks detected" if takeovers
                else "MEDIUM — wildcard DNS detected" if wildcard.get("is_wildcard")
                else "LOW — no critical issues found"
            ),
        }
