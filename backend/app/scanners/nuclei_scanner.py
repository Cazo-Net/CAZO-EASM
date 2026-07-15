import asyncio
import json
import shutil
import tempfile
import os
from typing import Any, Dict, List
from app.scanners.base import BaseScanner
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class NucleiScanner(BaseScanner):
    """Scanner for vulnerability detection using nuclei."""

    def __init__(self):
        super().__init__()
        self.nuclei_path = self._find_nuclei()

    def _find_nuclei(self) -> str:
        """Find nuclei binary path."""
        path = getattr(settings, "NUCLEI_PATH", "nuclei")
        if shutil.which(path):
            return path
        logger.warning("nuclei not found in PATH, vulnerability scanning disabled")
        return None

    def validate_target(self, target: str) -> bool:
        return bool(target and isinstance(target, str))

    async def scan(self, target: str, urls: List[str] = None, **kwargs) -> Dict[str, Any]:
        """Run nuclei vulnerability scan against target URLs."""
        if not self.nuclei_path:
            return self._format_error(Exception("nuclei binary not found"))

        if not urls:
            return {
                "success": True,
                "target": target,
                "vulnerabilities": [],
                "message": "No URLs to scan",
            }

        try:
            urls_file = os.path.join(tempfile.gettempdir(), f"nuclei_urls_{target.replace('.', '_')}.txt")
            with open(urls_file, "w") as f:
                f.write("\n".join(urls))

            cmd = [
                self.nuclei_path,
                "-l", urls_file,
                "-json",
                "-silent",
                "-severity", "critical,high,medium,low",
                "-timeout", "10",
                "-retries", "1",
                "-rate-limit", "50",
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

            try:
                import os
                os.remove(urls_file)
            except Exception:
                pass

            vulnerabilities = []
            if stdout:
                for line in stdout.decode().strip().split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        vuln = json.loads(line)
                        vulnerabilities.append({
                            "template_id": vuln.get("template-id", ""),
                            "name": vuln.get("info", {}).get("name", ""),
                            "severity": vuln.get("info", {}).get("severity", "unknown"),
                            "type": vuln.get("type", ""),
                            "host": vuln.get("host", ""),
                            "matched_at": vuln.get("matched-at", ""),
                            "description": vuln.get("info", {}).get("description", ""),
                            "reference": vuln.get("info", {}).get("reference", []),
                            "tags": vuln.get("info", {}).get("tags", []),
                        })
                    except json.JSONDecodeError:
                        continue

            return {
                "success": True,
                "target": target,
                "vulnerabilities": vulnerabilities,
                "count": len(vulnerabilities),
                "scanner": "nuclei",
            }

        except asyncio.TimeoutError:
            return self._format_error(Exception("nuclei scan timed out"))
        except Exception as e:
            return self._format_error(e)
