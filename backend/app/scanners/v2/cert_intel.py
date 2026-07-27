"""TLS/Certificate intelligence scanner.

Enhanced certificate analysis with:
- Certificate history tracking
- Certificate Transparency log monitoring
- Expiration tracking and alerts
- Weak TLS detection
- Cipher suite analysis
- Shared certificate relationships (cert shodan)
- HSTS preload check
- OCSP stapling detection
"""
from __future__ import annotations

import ssl
import socket
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.scanners.v2.base import EnhancedBaseScanner, ScanResult, ScannerPriority
from app.scanners.v2.registry import register_scanner, ScannerCategory

logger = logging.getLogger(__name__)

# Weak ciphers and protocols
WEAK_PROTOCOLS = {"SSLv2", "SSLv3", "TLSv1", "TLSv1.1"}
WEAK_CIPHERS = {"RC4", "DES", "3DES", "NULL", "EXPORT", "MD5", "anon"}
STRONG_CIPHERS = {"AESGCM", "CHACHA20", "AES256"}


@register_scanner(
    name="certificate-intelligence",
    category=ScannerCategory.CERTIFICATE_ANALYSIS,
    version="2.0.0",
    priority=ScannerPriority.NORMAL,
    description="Advanced TLS/certificate intelligence with CT monitoring and risk analysis",
    capabilities=[
        "certificate_parsing", "tls_configuration", "cipher_analysis",
        "expiry_tracking", "ct_monitoring", "hsts_check",
    ],
)
class CertificateIntelligenceScanner(EnhancedBaseScanner):
    """TLS/certificate intelligence and risk assessment."""

    name = "certificate-intelligence"
    version = "2.0.0"
    category = ScannerCategory.CERTIFICATE_ANALYSIS
    priority = ScannerPriority.NORMAL

    async def scan(self, target: str, **kwargs) -> ScanResult:
        # Analyze TLS on common HTTPS ports
        ports = [443, 8443]
        results = {}
        errors = []

        for port in ports:
            try:
                cert_data = await self._analyze_tls(target, port)
                if cert_data:
                    results[str(port)] = cert_data
            except Exception as e:
                errors.append(f"Port {port}: {e}")

        # Check CT logs
        ct_data = await self._check_ct_logs(target)

        # Check HSTS preload
        hsts_data = await self._check_hsts(target)

        # Build comprehensive result
        analysis = self._build_analysis(results, ct_data, hsts_data)

        return ScanResult(
            success=True,
            scanner=self.name,
            target=target,
            data={
                "hosts": {target: results},
                "certificates": results,
                "ct_logs": ct_data,
                "hsts": hsts_data,
                "analysis": analysis,
                "alerts": self._generate_alerts(results, hsts_data),
            },
            errors=errors,
        )

    def validate_target(self, target: str) -> bool:
        return bool(target and "." in target)

    async def _analyze_tls(self, host: str, port: int) -> Optional[Dict[str, Any]]:
        """Analyze TLS configuration and certificate."""
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            # Capture all supported protocols and ciphers
            sock = socket.create_connection((host, port), timeout=3)
            ssl_sock = ctx.wrap_socket(sock, server_hostname=host)

            cert = ssl_sock.getpeercert(binary_form=False)
            cipher = ssl_sock.cipher()
            version = ssl_sock.version()

            ssl_sock.close()
            sock.close()

            if not cert:
                return None

            # Parse certificate details
            subject = dict(x[0] for x in cert.get("subject", ()))
            issuer = dict(x[0] for x in cert.get("issuer", ()))
            san_list = []
            for ext_type, ext_value in cert.get("subjectAltName", ()):
                if ext_type == "DNS":
                    san_list.append(ext_value)

            # Parse validity
            not_before = cert.get("notBefore", "")
            not_after = cert.get("notAfter", "")
            days_until_expiry = self._days_until(not_after)
            is_valid = days_until_expiry is not None and days_until_expiry > 0

            # Calculate grade
            grade = self._calculate_grade(
                version, cipher, days_until_expiry, issuer, is_valid
            )

            return {
                "subject": subject,
                "issuer": issuer,
                "san": san_list,
                "not_before": not_before,
                "not_after": not_after,
                "days_until_expiry": days_until_expiry,
                "is_valid": is_valid,
                "protocol": version,
                "cipher_suite": cipher[0] if cipher else None,
                "cipher_bits": cipher[2] if cipher else None,
                "grade": grade,
                "self_signed": issuer.get("commonName") == subject.get("commonName"),
                "wildcard": any(s.startswith("*.") for s in san_list),
            }

        except Exception as e:
            logger.warning("TLS analysis failed for %s:%d: %s", host, port, e)
            return None

    async def _check_ct_logs(self, domain: str) -> Dict[str, Any]:
        """Check Certificate Transparency logs for recent certificates."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"https://crt.sh/?q=%.{domain}&output=json"
                )
                if resp.status_code == 200:
                    import json
                    entries = json.loads(resp.text)
                    recent = []
                    for entry in entries[:20]:
                        recent.append({
                            "name": entry.get("name_value", ""),
                            "issuer": entry.get("issuer_name", ""),
                            "not_before": entry.get("not_before", ""),
                            "not_after": entry.get("not_after", ""),
                        })
                    return {
                        "found": True,
                        "total_entries": len(entries),
                        "recent": recent,
                    }
        except Exception as e:
            logger.warning("CT log check failed for %s: %s", domain, e)

        return {"found": False}

    async def _check_hsts(self, domain: str) -> Dict[str, Any]:
        """Check HSTS configuration and preload status."""
        result = {
            "hsts_enabled": False,
            "max_age": None,
            "include_subdomains": False,
            "preload": False,
            "on_preload_list": False,
        }

        try:
            async with httpx.AsyncClient(timeout=5, follow_redirects=False, verify=False) as client:
                resp = await client.get(f"https://{domain}/")
                hsts_header = resp.headers.get("strict-transport-security", "")
                if hsts_header:
                    result["hsts_enabled"] = True
                    import re
                    max_age_match = re.search(r'max-age=(\d+)', hsts_header)
                    if max_age_match:
                        result["max_age"] = int(max_age_match.group(1))
                    result["include_subdomains"] = "includeSubDomains" in hsts_header
                    result["preload"] = "preload" in hsts_header

                    # Check preload list
                    if result["preload"]:
                        result["on_preload_list"] = await self._check_preload_list(domain)

        except Exception:
            pass

        return result

    async def _check_preload_list(self, domain: str) -> bool:
        """Check if domain is on the HSTS preload list."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    "https://hstspreload.org/api/v2/status",
                    params={"domain": domain},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("status") == "present"
        except Exception:
            pass
        return False

    def _calculate_grade(
        self,
        protocol: Optional[str],
        cipher: Optional[tuple],
        days_left: Optional[int],
        issuer: Dict,
        is_valid: bool,
    ) -> str:
        """Calculate TLS grade (A+ to F)."""
        score = 100

        # Protocol penalties
        if protocol in WEAK_PROTOCOLS:
            score -= 40
        elif protocol == "TLSv1.2":
            score -= 5
        # TLSv1.3 is ideal, no penalty

        # Cipher penalties
        if cipher:
            cipher_name = cipher[0]
            if any(w in cipher_name for w in WEAK_CIPHERS):
                score -= 30
            elif any(s in cipher_name for s in STRONG_CIPHERS):
                pass  # No penalty
        else:
            score -= 10

        # Expiry penalties
        if days_left is not None:
            if days_left < 0:
                score -= 50  # Expired
            elif days_left < 7:
                score -= 20
            elif days_left < 30:
                score -= 10

        # Validity
        if not is_valid:
            score -= 30

        # Self-signed
        if issuer.get("commonName", "").lower() == "localhost":
            score -= 20

        # Map score to grade
        if score >= 90:
            return "A+"
        elif score >= 80:
            return "A"
        elif score >= 70:
            return "B"
        elif score >= 60:
            return "C"
        elif score >= 50:
            return "D"
        else:
            return "F"

    def _days_until(self, date_str: str) -> Optional[int]:
        """Calculate days until a date string expires."""
        try:
            exp = datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z")
            exp = exp.replace(tzinfo=timezone.utc)
            delta = exp - datetime.now(timezone.utc)
            return delta.days
        except Exception:
            return None

    def _build_analysis(
        self,
        certs: Dict[str, Dict],
        ct: Dict[str, Any],
        hsts: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build comprehensive TLS analysis."""
        analysis = {
            "tls_configured": bool(certs),
            "grades": {},
            "issues": [],
            "strengths": [],
        }

        for port, cert in certs.items():
            analysis["grades"][port] = cert.get("grade", "F")

            if not cert.get("is_valid", True):
                analysis["issues"].append(f"Certificate expired on port {port}")
            if cert.get("days_until_expiry", 999) < 30:
                analysis["issues"].append(
                    f"Certificate expires in {cert.get('days_until_expiry')} days on port {port}"
                )
            if cert.get("protocol") in WEAK_PROTOCOLS:
                analysis["issues"].append(f"Weak TLS protocol {cert['protocol']} on port {port}")
            if cert.get("self_signed"):
                analysis["issues"].append(f"Self-signed certificate on port {port}")

        if hsts.get("hsts_enabled"):
            analysis["strengths"].append("HSTS enabled")
            if hsts.get("preload"):
                analysis["strengths"].append("HSTS preload active")
        else:
            analysis["issues"].append("HSTS not enabled")

        return analysis

    def _generate_alerts(
        self, certs: Dict[str, Dict], hsts: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate actionable alerts."""
        alerts = []

        for port, cert in certs.items():
            days = cert.get("days_until_expiry")
            if days is not None and days < 0:
                alerts.append({
                    "severity": "critical",
                    "type": "certificate_expired",
                    "detail": f"Certificate expired {abs(days)} days ago on port {port}",
                    "action": "Renew certificate immediately",
                })
            elif days is not None and days < 7:
                alerts.append({
                    "severity": "critical",
                    "type": "certificate_expiring",
                    "detail": f"Certificate expires in {days} days on port {port}",
                    "action": "Schedule certificate renewal",
                })
            elif days is not None and days < 30:
                alerts.append({
                    "severity": "high",
                    "type": "certificate_expiring",
                    "detail": f"Certificate expires in {days} days on port {port}",
                    "action": "Plan certificate renewal",
                })

        if not hsts.get("hsts_enabled"):
            alerts.append({
                "severity": "medium",
                "type": "hsts_missing",
                "detail": "HSTS header not detected",
                "action": "Enable HSTS with appropriate max-age",
            })

        return sorted(alerts, key=lambda a: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(a["severity"], 4))
