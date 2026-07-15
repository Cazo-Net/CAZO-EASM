import asyncio
import json
import shutil
from typing import Any, Dict, List
from app.scanners.base import BaseScanner
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class SubfinderScanner(BaseScanner):
    """Scanner for subdomain discovery using subfinder."""

    def __init__(self):
        super().__init__()
        self.subfinder_path = self._find_subfinder()

    def _find_subfinder(self) -> str:
        """Find subfinder binary path."""
        path = getattr(settings, "SUBFINDER_PATH", "subfinder")
        if shutil.which(path):
            return path
        logger.warning("subfinder not found in PATH")
        return None

    def validate_target(self, target: str) -> bool:
        import re
        domain_regex = re.compile(
            r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        )
        return bool(domain_regex.match(target))

    async def scan(self, target: str, **kwargs) -> Dict[str, Any]:
        """Discover subdomains using subfinder."""
        if not self.subfinder_path:
            return {
                "success": True,
                "target": target,
                "subdomains": [],
                "count": 0,
                "message": "subfinder not available",
                "scanner": "subfinder",
            }

        if not self.validate_target(target):
            return self._format_error(ValueError(f"Invalid domain: {target}"))

        try:
            cmd = [
                self.subfinder_path,
                "-d", target,
                "-silent",
                "-json",
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout,
            )

            subdomains = set()
            if stdout:
                for line in stdout.decode().strip().split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        host = data.get("host", "")
                        if host:
                            subdomains.add(host)
                    except json.JSONDecodeError:
                        if line and "." in line:
                            subdomains.add(line)

            return {
                "success": True,
                "target": target,
                "subdomains": sorted(subdomains),
                "count": len(subdomains),
                "scanner": "subfinder",
            }

        except asyncio.TimeoutError:
            return self._format_error(Exception("subfinder scan timed out"))
        except Exception as e:
            return self._format_error(e)
