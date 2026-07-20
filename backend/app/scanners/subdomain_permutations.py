import asyncio
import dns.resolver
import dns.exception
from typing import Any, Dict, List, Optional, Set
from app.scanners.base import BaseScanner
from app.scanners.registry import register_scanner, ScannerCategory
import logging

logger = logging.getLogger(__name__)


@register_scanner(
    name="subdomain-permutations",
    category=ScannerCategory.SUBDOMAIN,
    description="Pure-Python subdomain permutation/mutation enumeration (no amass binary).",
)
class SubdomainPermutationScanner(BaseScanner):
    """Generate candidate subdomains by mutating already-known subdomains.

    Replaces amass's permutation discovery with pure string generation:
    prefix/suffix patterns (dev-, -old, .dev, numbers) applied to discovered
    subs, then DNS-checked. Only emits subs that resolve.
    """

    PREFIXES = ["dev", "staging", "stage", "test", "qa", "uat", "demo", "beta",
                "old", "new", "prod", "preprod", "api", "admin", "secure", "internal"]
    SUFFIXES = ["dev", "stage", "staging", "test", "qa", "uat", "demo", "beta",
                "old", "new", "prod", "backup", "bak", "int", "internal", "v2", "v1"]

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.concurrency = int(self.config.get("permutation_concurrency", 200))
        self.resolver_timeout = float(self.config.get("resolver_timeout", 2.0))

    def validate_target(self, target: str) -> bool:
        import re
        return bool(re.match(r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$', target))

    def _candidates(self, known: List[str], target: str) -> Set[str]:
        """Produce mutation candidates from already-known subdomains."""
        cands: Set[str] = set()
        labels = set()
        for sub in known:
            sub = sub.strip().lower()
            if sub == target:
                continue
            if sub.endswith(f".{target}"):
                sub = sub[: -(len(target) + 1)]
            # strip a leading known prefix/suffix to expose the "base" token
            base = sub
            for p in self.PREFIXES + self.SUFFIXES:
                if base.startswith(f"{p}-"):
                    base = base[len(p) + 1:]
                if base.endswith(f"-{p}"):
                    base = base[: -(len(p) + 1)]
            if not base or "." in base:
                # already multi-label; still try mutating the left-most label
                base = sub.split(".")[0]
            labels.add(base)

        for base in labels:
            for p in self.PREFIXES:
                cands.add(f"{p}-{base}.{target}")
                cands.add(f"{p}{base}.{target}")
            for s in self.SUFFIXES:
                cands.add(f"{base}-{s}.{target}")
                cands.add(f"{base}{s}.{target}")
            # numeric variants
            for i in range(1, 6):
                cands.add(f"{base}{i}.{target}")
                cands.add(f"{base}-{i}.{target}")
        return cands

    async def scan(self, target: str, known_subdomains: Optional[List[str]] = None, **kwargs) -> Dict[str, Any]:
        if not self.validate_target(target):
            return self._format_error(ValueError(f"Invalid domain: {target}"))

        known = known_subdomains or [target]
        cands = self._candidates(known, target)
        if not cands:
            return {"success": True, "target": target, "subdomains": [], "count": 0,
                    "scanner": "dns-permutations", "status": "no_candidates",
                    "candidates_tested": 0}

        resolver = dns.resolver.Resolver()
        resolver.lifetime = self.resolver_timeout
        resolver.timeout = self.resolver_timeout
        sem = asyncio.Semaphore(self.concurrency)
        found: Set[str] = set()

        async def resolve(host: str) -> None:
            async with sem:
                try:
                    await asyncio.to_thread(resolver.resolve, host, "A")
                    found.add(host.lower())
                except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer,
                        dns.resolver.NoNameservers, dns.exception.Timeout,
                        dns.exception.DNSException, OSError):
                    pass

        await asyncio.gather(*[resolve(c) for c in cands], return_exceptions=True)

        # Exclude anything already in the known set.
        known_set = {k.lower().rstrip(".") for k in known}
        result = sorted(f for f in found if f not in known_set)
        return {
            "success": True,
            "target": target,
            "subdomains": result,
            "count": len(result),
            "scanner": "dns-permutations",
            "status": "ok" if result else "no_results",
            "candidates_tested": len(cands),
        }
