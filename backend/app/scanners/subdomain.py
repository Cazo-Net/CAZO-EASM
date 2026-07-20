import asyncio
import httpx
import json
import re
from typing import Any, Dict, List, Set, Tuple
from app.scanners.base import BaseScanner
from app.scanners.registry import register_scanner, ScannerCategory
from app.config import settings
import logging

logger = logging.getLogger(__name__)


@register_scanner(
    name="subdomain",
    category=ScannerCategory.SUBDOMAIN,
    description="Multi-source subdomain enumeration (crt.sh, RapidDNS, URLScan, AlienVault, HackerTarget).",
)
class SubdomainScanner(BaseScanner):
    """Multi-source subdomain discovery via free APIs."""

    CRTSH_URL = "https://crt.sh/"
    HACKERTARGET_URL = "https://api.hackertarget.com/hostsearch/"
    ALIENVAULT_URL = "https://otx.alienvault.com/api/v1/indicators/domain/"
    RAPIDDNS_URL = "https://rapiddns.io/subdomain/"
    URLSCAN_URL = "https://urlscan.io/api/v1/search/"

    def validate_target(self, target: str) -> bool:
        domain_regex = re.compile(
            r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        )
        return bool(domain_regex.match(target))

    def _is_valid_subdomain(self, name: str, target: str) -> bool:
        """Check if name is a valid subdomain of target."""
        name = name.strip().lower()
        if not name or name == target:
            return False
        if "@" in name:
            return False
        if name.startswith("*."):
            name = name[2:]
        if not name or name == target:
            return False
        if name.endswith(f".{target}") or name == target:
            return bool(re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*$', name))
        return False

    async def _fetch_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
        retries: int = 2,
        timeout: int = 15,
    ) -> httpx.Response | None:
        """Fetch a URL with linear backoff retry."""
        last_err = None
        for attempt in range(retries):
            try:
                return await client.get(url, params=params, headers=headers, timeout=timeout)
            except Exception as e:
                last_err = e
                if attempt < retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
        logger.warning(f"Fetch failed after {retries} attempts: {url} ({last_err})")
        return None

    async def _crtsh(self, client: httpx.AsyncClient, target: str) -> Set[str]:
        """Source 1: crt.sh certificate transparency."""
        subdomains = set()
        try:
            response = await self._fetch_with_retry(
                client,
                self.CRTSH_URL,
                params={"q": f"%.{target}", "output": "json"},
                timeout=15,
            )
            if response is not None and response.status_code == 200:
                data = response.json()
                for entry in data:
                    name_value = entry.get("name_value", "")
                    for name in name_value.split("\n"):
                        name = name.strip().lower()
                        if self._is_valid_subdomain(name, target):
                            if name.startswith("*."):
                                name = name[2:]
                            if name.endswith(f".{target}"):
                                subdomains.add(name)
                logger.info(f"crt.sh found {len(subdomains)} subdomains for {target}")
        except Exception as e:
            logger.warning(f"crt.sh failed: {e}")
        return subdomains

    async def _rapiddns(self, client: httpx.AsyncClient, target: str) -> Set[str]:
        """Source: RapidDNS (HTML parse)."""
        subdomains = set()
        try:
            response = await self._fetch_with_retry(
                client,
                f"{self.RAPIDDNS_URL}{target}",
                params={"full": "1"},
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                timeout=25,
            )
            if response is not None and response.status_code == 200:
                # RapidDNS embeds hostnames in <td> cells; capture the full
                # hostname (one or more labels followed by the target domain).
                pattern = r'([a-zA-Z0-9_\-]+(?:\.[a-zA-Z0-9_\-]+)*\.' + re.escape(target) + r')(?=<|")'
                for m in re.finditer(pattern, response.text):
                    name = m.group(1).lower()
                    if self._is_valid_subdomain(name, target):
                        subdomains.add(name)
                logger.info(f"RapidDNS found {len(subdomains)} subdomains for {target}")
        except Exception as e:
            logger.warning(f"RapidDNS failed: {e}")
        return subdomains

    async def _urlscan(self, client: httpx.AsyncClient, target: str) -> Set[str]:
        """Source: URLScan.io passive discovery."""
        subdomains = set()
        try:
            response = await self._fetch_with_retry(
                client,
                self.URLSCAN_URL,
                params={"q": f"domain:{target}"},
                timeout=25,
            )
            if response is not None and response.status_code == 200:
                data = response.json()
                for res in data.get("results", []):
                    dom = res.get("page", {}).get("domain", "")
                    if dom and self._is_valid_subdomain(dom, target):
                        subdomains.add(dom.lower())
                logger.info(f"URLScan found {len(subdomains)} subdomains for {target}")
        except Exception as e:
            logger.warning(f"URLScan failed: {e}")
        return subdomains

    async def _hackertarget(self, client: httpx.AsyncClient, target: str) -> Set[str]:
        """Source: HackerTarget API."""
        subdomains = set()
        try:
            response = await self._fetch_with_retry(
                client,
                self.HACKERTARGET_URL,
                params={"q": target},
                timeout=20,
            )
            if response is not None and response.status_code == 200:
                for line in response.text.strip().split("\n"):
                    if "," in line:
                        hostname = line.split(",")[0].strip().lower()
                        if self._is_valid_subdomain(hostname, target):
                            subdomains.add(hostname)
                logger.info(f"HackerTarget found {len(subdomains)} subdomains for {target}")
        except Exception as e:
            logger.warning(f"HackerTarget failed: {e}")
        return subdomains

    async def _alienvault(self, client: httpx.AsyncClient, target: str) -> Set[str]:
        """Source: AlienVault OTX."""
        subdomains = set()
        try:
            response = await self._fetch_with_retry(
                client,
                f"{self.ALIENVAULT_URL}{target}/passive_dns",
                headers={"Accept": "application/json"},
                timeout=20,
            )
            if response is not None and response.status_code == 200:
                data = response.json()
                for record in data.get("passive_dns", []):
                    hostname = record.get("hostname", "").strip().lower()
                    if self._is_valid_subdomain(hostname, target):
                        subdomains.add(hostname)
                logger.info(f"AlienVault found {len(subdomains)} subdomains for {target}")
        except Exception as e:
            logger.warning(f"AlienVault failed: {e}")
        return subdomains

    async def scan(self, target: str, use_all_sources: bool = True, **kwargs) -> Dict[str, Any]:
        """Discover subdomains using multiple free sources."""
        if not self.validate_target(target):
            return self._format_error(ValueError(f"Invalid domain: {target}"))

        subdomains = set()
        subdomains.add(target)

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": "CAZO/1.0 (security scanner)"},
        ) as client:
            sources = [self._crtsh(client, target), self._rapiddns(client, target), self._urlscan(client, target)]
            # The following sources are often rate-limited on dev machines; only
            # include them when explicitly asked to use all sources.
            if use_all_sources:
                sources.extend([self._hackertarget(client, target), self._alienvault(client, target)])

            results = await asyncio.gather(*sources, return_exceptions=True)

            for result in results:
                if isinstance(result, set):
                    subdomains.update(result)

        subdomains = sorted(subdomains)

        return {
            "success": True,
            "target": target,
            "subdomains": subdomains,
            "count": len(subdomains),
            "scanner": "multi-source",
        }
