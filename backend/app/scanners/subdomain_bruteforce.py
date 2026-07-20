import asyncio
import os
import dns.resolver
import dns.exception
from typing import Any, Dict, List, Optional, Set
from app.scanners.base import BaseScanner
from app.scanners.registry import register_scanner, ScannerCategory
import logging

logger = logging.getLogger(__name__)

_WORDLIST_PATH = os.path.join(os.path.dirname(__file__), "data", "subdomains_2000.txt")


@register_scanner(
    name="subdomain-bruteforce",
    category=ScannerCategory.SUBDOMAIN,
    description="Pure-Python DNS brute-force subdomain enumeration (no amass binary).",
)
class SubdomainBruteforceScanner(BaseScanner):
    """Concurrent DNS A/AAAA lookups against a wordlist.

    Replaces amass's active DNS brute-force with pure dnspython. Uses a bounded
    worker pool so it stays gentle on resolvers and runs on serverless. Only
    emits subdomains that actually resolve (honest: no guessing/assumptions).
    """

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.concurrency = int(self.config.get("bruteforce_concurrency", 200))
        self.resolver_timeout = float(self.config.get("resolver_timeout", 2.0))
        self.wordlist_path = self.config.get("wordlist_path", _WORDLIST_PATH)

    def validate_target(self, target: str) -> bool:
        import re
        return bool(re.match(r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$', target))

    def _load_words(self) -> List[str]:
        try:
            with open(self.wordlist_path, "r") as f:
                return [w.strip() for w in f if w.strip()]
        except FileNotFoundError:
            logger.warning("Wordlist not found: %s", self.wordlist_path)
            return []

    async def scan(self, target: str, wordlist: Optional[List[str]] = None, **kwargs) -> Dict[str, Any]:
        if not self.validate_target(target):
            return self._format_error(ValueError(f"Invalid domain: {target}"))

        words = wordlist or self._load_words()
        if not words:
            return {
                "success": True, "target": target, "subdomains": [],
                "count": 0, "scanner": "dns-bruteforce", "status": "no_wordlist",
            }

        resolver = dns.resolver.Resolver()
        resolver.lifetime = self.resolver_timeout
        resolver.timeout = self.resolver_timeout
        sem = asyncio.Semaphore(self.concurrency)
        found: Set[str] = set()

        async def resolve(word: str) -> None:
            host = f"{word}.{target}"
            async with sem:
                try:
                    # A/AAAA lookup; success => subdomain exists.
                    await asyncio.to_thread(resolver.resolve, host, "A")
                    found.add(host.lower())
                except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer,
                        dns.resolver.NoNameservers, dns.exception.Timeout,
                        dns.exception.DNSException, OSError):
                    pass
                except Exception as e:  # unexpected
                    logger.debug("bruteforce %s error: %s", host, e)

        await asyncio.gather(*[resolve(w) for w in words], return_exceptions=True)

        result = sorted(found)
        return {
            "success": True,
            "target": target,
            "subdomains": result,
            "count": len(result),
            "scanner": "dns-bruteforce",
            "status": "ok" if result else "no_results",
            "wordlist_size": len(words),
        }
