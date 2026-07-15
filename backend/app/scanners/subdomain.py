import asyncio
import httpx
import json
from typing import Any, Dict, Set
from app.scanners.base import BaseScanner
import re
import logging

logger = logging.getLogger(__name__)


class SubdomainScanner(BaseScanner):
    """Multi-source subdomain discovery via free APIs."""

    CRTSH_URL = "https://crt.sh/"
    HACKERTARGET_URL = "https://api.hackertarget.com/hostsearch/"
    ALIENVAULT_URL = "https://otx.alienvault.com/api/v1/indicators/domain/"

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

    async def _crtsh(self, client: httpx.AsyncClient, target: str) -> Set[str]:
        """Source 1: crt.sh certificate transparency."""
        subdomains = set()
        try:
            response = await client.get(
                self.CRTSH_URL,
                params={"q": f"%.{target}", "output": "json"},
                timeout=30,
            )
            if response.status_code == 200:
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

    async def _hackertarget(self, client: httpx.AsyncClient, target: str) -> Set[str]:
        """Source 2: HackerTarget API."""
        subdomains = set()
        try:
            response = await client.get(
                self.HACKERTARGET_URL,
                params={"q": target},
                timeout=20,
            )
            if response.status_code == 200:
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
        """Source 3: AlienVault OTX."""
        subdomains = set()
        try:
            response = await client.get(
                f"{self.ALIENVAULT_URL}{target}/passive_dns",
                headers={"Accept": "application/json"},
                timeout=20,
            )
            if response.status_code == 200:
                data = response.json()
                for record in data.get("passive_dns", []):
                    hostname = record.get("hostname", "").strip().lower()
                    if self._is_valid_subdomain(hostname, target):
                        subdomains.add(hostname)
                logger.info(f"AlienVault found {len(subdomains)} subdomains for {target}")
        except Exception as e:
            logger.warning(f"AlienVault failed: {e}")
        return subdomains

    async def scan(self, target: str, **kwargs) -> Dict[str, Any]:
        """Discover subdomains using multiple free sources."""
        if not self.validate_target(target):
            return self._format_error(ValueError(f"Invalid domain: {target}"))

        subdomains = set()
        subdomains.add(target)

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": "AttackSec/1.0 (security scanner)"},
        ) as client:
            results = await asyncio.gather(
                self._crtsh(client, target),
                self._hackertarget(client, target),
                self._alienvault(client, target),
                return_exceptions=True,
            )

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
