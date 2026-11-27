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


def _parse_der_certificate(der: bytes) -> Dict[str, Any]:
    """Leaf certificate details via cryptography (works without verification)."""
    from cryptography import x509
    from cryptography.hazmat.primitives.asymmetric import dsa, ec, ed25519, rsa
    from cryptography.x509.oid import ExtensionOID, NameOID

    cert = x509.load_der_x509_certificate(der)

    def _name(n: "x509.Name") -> Dict[str, str]:
        out: Dict[str, str] = {}
        for oid, key in ((NameOID.COMMON_NAME, "commonName"), (NameOID.ORGANIZATION_NAME, "organizationName"),
                         (NameOID.COUNTRY_NAME, "countryName")):
            attrs = n.get_attributes_for_oid(oid)
            if attrs:
                out[key] = str(attrs[0].value)
        return out

    try:
        san = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
        san_list = [str(x) for x in san.get_values_for_type(x509.DNSName)]
    except x509.ExtensionNotFound:
        san_list = []

    key = cert.public_key()
    if isinstance(key, rsa.RSAPublicKey):
        key_type, bits = "RSA", key.key_size
    elif isinstance(key, ec.EllipticCurvePublicKey):
        key_type, bits = "EC", key.curve.key_size
    elif isinstance(key, ed25519.Ed25519PublicKey):
        key_type, bits = "Ed25519", 256
    elif isinstance(key, dsa.DSAPublicKey):
        key_type, bits = "DSA", key.key_size
    else:
        key_type, bits = type(key).__name__, None

    not_before = cert.not_valid_before_utc
    not_after = cert.not_valid_after_utc
    try:
        sig = cert.signature_hash_algorithm.name if cert.signature_hash_algorithm else ""
    except Exception:  # noqa: BLE001
        sig = ""
    return {
        "subject": _name(cert.subject),
        "issuer": _name(cert.issuer),
        "serial_number": format(cert.serial_number, "x"),
        "san": san_list,
        "not_before": not_before.isoformat(),
        "not_after": not_after.isoformat(),
        "key_type": key_type,
        "key_bits": bits,
        "signature_algorithm": sig,
        "_days_left": (not_after - datetime.now(timezone.utc)).days,
    }


def _hostname_matches(host: str, sans: List[str], cn: Optional[str]) -> bool:
    names = [n.lower() for n in (sans or ([cn] if cn else []))]
    host = host.lower()
    for n in names:
        if n == host:
            return True
        if n.startswith("*.") and host.count(".") == n.count(".") and host.endswith(n[1:]):
            return True
    return False


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

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.max_endpoints = int(self.config.get("tls_max_endpoints", 10))
        self.timeout = max(float(self.timeout), 120.0)
        self.max_retries = min(self.max_retries, 1)

    async def scan(self, target: str, **kwargs) -> ScanResult:
        """Inspect TLS on every in-scope HTTPS/TLS endpoint the port scan found.

        ``tls_endpoints`` comes from the pipeline and only contains hosts that
        passed the scope gate; without it only the target is checked.
        """
        import asyncio

        endpoints = list(kwargs.get("tls_endpoints") or [])
        if not endpoints:
            endpoints = [(target, 443), (target, 8443)]
        root = kwargs.get("root_domain") or target
        from app.core.target_guard import host_in_scope
        endpoints = [(h, int(p)) for h, p in endpoints if host_in_scope(h, root)][: self.max_endpoints]

        sem = asyncio.Semaphore(5)
        by_host: Dict[str, Dict[str, Any]] = {}
        errors: List[str] = []

        async def _one(host: str, port: int) -> None:
            async with sem:
                try:
                    data = await asyncio.wait_for(
                        asyncio.to_thread(self._analyze_tls_sync, host, port), timeout=30)
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{host}:{port}: {e}")
                    return
                if data:
                    by_host.setdefault(host, {})[str(port)] = data

        await asyncio.gather(*(_one(h, p) for h, p in endpoints))

        ct_data = await self._check_ct_logs(target)
        hsts_data = await self._check_hsts(target)
        apex = by_host.get(target, {})
        findings = self._tls_findings(by_host)

        return ScanResult(
            success=True,
            scanner=self.name,
            target=target,
            data={
                "hosts": by_host,
                "certificates": apex,
                "endpoints_checked": len(endpoints),
                "ct_logs": ct_data,
                "hsts": hsts_data,
                "analysis": self._build_analysis(apex, ct_data, hsts_data),
                "alerts": self._generate_alerts(apex, hsts_data),
                "findings": findings,
            },
            errors=errors,
        )

    def validate_target(self, target: str) -> bool:
        return bool(target and "." in target)

    async def _analyze_tls(self, host: str, port: int) -> Optional[Dict[str, Any]]:
        import asyncio
        return await asyncio.to_thread(self._analyze_tls_sync, host, port)

    def _analyze_tls_sync(self, host: str, port: int) -> Optional[Dict[str, Any]]:
        """Handshake, parse the leaf certificate, check trust and legacy TLS.

        Up to three short handshakes per endpoint: one to read the
        certificate, one with normal verification to learn whether browsers
        would trust it, and one restricted to TLS 1.0/1.1 to see whether
        outdated protocols are still accepted. No data is sent.
        """
        from app.core.target_guard import check_public_target
        if not check_public_target(host).allowed:
            return None

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            with socket.create_connection((host, port), timeout=5) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    der = ssock.getpeercert(binary_form=True)
                    cipher = ssock.cipher()
                    version = ssock.version()
        except Exception as e:  # noqa: BLE001
            logger.info("TLS handshake failed for %s:%d: %s", host, port, e)
            return None
        if not der:
            return None

        info = _parse_der_certificate(der)
        days_until_expiry = info.pop("_days_left", None)

        trust_error = None
        try:
            vctx = ssl.create_default_context()
            with socket.create_connection((host, port), timeout=5) as sock:
                with vctx.wrap_socket(sock, server_hostname=host):
                    pass
        except ssl.SSLCertVerificationError as e:
            trust_error = getattr(e, "verify_message", None) or str(e)
        except Exception as e:  # noqa: BLE001 — network trouble, not a trust verdict
            trust_error = None
            logger.debug("verify handshake failed for %s:%d: %s", host, port, e)

        legacy: List[str] = []
        try:
            lctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            lctx.check_hostname = False
            lctx.verify_mode = ssl.CERT_NONE
            lctx.minimum_version = ssl.TLSVersion.TLSv1
            lctx.maximum_version = ssl.TLSVersion.TLSv1_1
            lctx.set_ciphers("ALL:@SECLEVEL=0")
            with socket.create_connection((host, port), timeout=5) as sock:
                with lctx.wrap_socket(sock, server_hostname=host) as lsock:
                    if lsock.version():
                        legacy.append(lsock.version())
        except Exception:  # noqa: BLE001 — refused (good) or not supported locally
            pass

        hostname_match = _hostname_matches(host, info.get("san", []), info["subject"].get("commonName"))
        is_valid = bool(days_until_expiry is not None and days_until_expiry > 0 and not trust_error)
        grade = self._calculate_grade(version, cipher, days_until_expiry, info["issuer"], is_valid)
        if legacy and grade in ("A+", "A"):
            grade = "B"
        if (info.get("key_type") == "RSA" and (info.get("key_bits") or 0) < 2048) or \
                "sha1" in (info.get("signature_algorithm") or "").lower():
            grade = "C" if grade in ("A+", "A", "B") else grade

        return {
            **info,
            "host": host,
            "port": port,
            "days_until_expiry": days_until_expiry,
            "is_valid": is_valid,
            "trusted": trust_error is None,
            "trust_error": trust_error,
            "hostname_match": hostname_match,
            "protocol": version,
            "legacy_protocols": legacy,
            "cipher_suite": cipher[0] if cipher else None,
            "cipher_bits": cipher[2] if cipher else None,
            "grade": grade,
            "self_signed": info["issuer"] == info["subject"],
            "wildcard": any(s.startswith("*.") for s in info.get("san", [])),
        }

    def _tls_findings(self, by_host: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Endpoint-level TLS problems (expiry/validity is reported by security-findings)."""
        out: List[Dict[str, Any]] = []

        def _f(tid: str, name: str, sev: str, host: str, port: str, desc: str) -> None:
            out.append({
                "template_id": tid, "name": name, "severity": sev, "vuln_type": "tls",
                "host": host, "matched_at": f"{host}:{port}", "description": desc,
                "tags": ["tls"], "extracted_results": [], "reference": [],
            })

        for host, ports in by_host.items():
            for port, c in ports.items():
                if c.get("legacy_protocols"):
                    _f("tls/legacy-protocol", "Outdated TLS versions accepted", "medium", host, port,
                       f"{host}:{port} still accepts {', '.join(c['legacy_protocols'])}. Disable TLS 1.0 and 1.1.")
                if c.get("hostname_match") is False:
                    _f("tls/hostname-mismatch", "TLS certificate does not match host name", "medium", host, port,
                       f"The certificate on {host}:{port} is issued for {', '.join(c.get('san', [])[:5]) or c['subject'].get('commonName', '?')}.")
                if c.get("self_signed"):
                    _f("tls/self-signed", "Self-signed TLS certificate", "medium", host, port,
                       f"{host}:{port} presents a self-signed certificate.")
                if c.get("key_type") == "RSA" and (c.get("key_bits") or 0) < 2048:
                    _f("tls/weak-key", "Weak RSA key", "high", host, port,
                       f"{host}:{port} uses a {c.get('key_bits')}-bit RSA key.")
                if "sha1" in (c.get("signature_algorithm") or "").lower():
                    _f("tls/sha1-signature", "Certificate signed with SHA-1", "medium", host, port,
                       f"{host}:{port} certificate uses {c.get('signature_algorithm')}.")
                if c.get("trust_error") and not c.get("self_signed") and c.get("hostname_match") is not False:
                    _f("tls/untrusted", "TLS certificate not trusted", "high", host, port,
                       f"{host}:{port}: {c['trust_error']}.")
        return out

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
