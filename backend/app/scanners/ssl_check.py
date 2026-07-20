import asyncio
import ssl
import socket
from typing import Any, Dict, List, Optional, Tuple
from app.scanners.base import BaseScanner
from app.scanners.registry import register_scanner, ScannerCategory
from datetime import datetime
import logging

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import rsa, ec, dsa

logger = logging.getLogger(__name__)


# Protocols we consider weak / deprecated.
_WEAK_PROTOCOLS = {"SSLv2", "SSLv3", "TLSv1", "TLSv1.1"}
# Cipher substrings that are broken or discouraged.
_WEAK_CIPHER_MARKERS = ["RC4", "DES", "3DES", "NULL", "EXPORT", "MD5"]


def _ssl_connect_sync(target: str, port: int):
    """Synchronous SSL connect — runs in a thread."""
    context = ssl.create_default_context()
    context.set_ciphers("ALL:@SECLEVEL=0")
    der_certs: List[bytes] = []
    with socket.create_connection((target, port), timeout=8) as sock:
        with context.wrap_socket(sock, server_hostname=target) as ssock:
            cert = ssock.getpeercert()
            cipher = ssock.cipher()
            version = ssock.version()
            try:
                der_certs = ssock.getpeercert(binary_form=True)
                if isinstance(der_certs, bytes):
                    der_certs = [der_certs]
            except Exception:
                der_certs = []
    return cert, cipher, version, der_certs


@register_scanner(
    name="ssl",
    category=ScannerCategory.SSL,
    description="SSL/TLS certificate analysis and grading.",
)
class SSLScanner(BaseScanner):
    """Scanner for SSL/TLS certificate analysis."""
    
    def validate_target(self, target: str) -> bool:
        """Validate hostname format."""
        import re
        hostname_regex = re.compile(
            r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        )
        return bool(hostname_regex.match(target))
    
    async def scan(self, target: str, port: int = 443, **kwargs) -> Dict[str, Any]:
        """Analyze SSL/TLS certificate."""
        if not self.validate_target(target):
            return self._format_error(ValueError(f"Invalid hostname: {target}"))
        
        try:
            # Run the blocking SSL connect in a thread
            cert, cipher, version, der_certs = await asyncio.wait_for(
                asyncio.to_thread(_ssl_connect_sync, target, port),
                timeout=12,
            )
            
            if not cert:
                return {
                    "success": True,
                    "target": target,
                    "certificate": None,
                    "error": "No certificate found",
                    "scanner": "ssl"
                }
            
            # Parse certificate info
            subject = dict(x[0] for x in cert.get('subject', []))
            issuer = dict(x[0] for x in cert.get('issuer', []))
            
            # Parse dates
            not_before = datetime.strptime(cert['notBefore'], '%b %d %H:%M:%S %Y %Z')
            not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
            
            # Calculate days until expiry
            days_until_expiry = (not_after - datetime.now()).days
            
            # Weak protocol / cipher flags
            flags = self._weak_flags(version, cipher)
            
            # Calculate grade (also considers weak flags)
            grade = self._calculate_grade(cert, version, cipher, days_until_expiry, flags)
            
            # Get SANs
            san_names = []
            san_ips = []
            if 'subjectAltName' in cert:
                for san_type, san_value in cert['subjectAltName']:
                    if san_type == 'DNS':
                        san_names.append(san_value)
                    elif san_type == 'IP Address':
                        san_ips.append(san_value)
            
            # Chain walk (leaf + intermediate certs, if provided by server).
            chain_info = self._analyze_chain(der_certs) if der_certs else None
            
            result = {
                "success": True,
                "target": target,
                "certificate": {
                    "subject": subject.get('commonName', target),
                    "issuer": issuer.get('organizationName', issuer.get('commonName', 'Unknown')),
                    "serial_number": cert.get('serialNumber', ''),
                    "not_before": not_before.isoformat(),
                    "not_after": not_after.isoformat(),
                    "days_until_expiry": days_until_expiry,
                    "is_valid": days_until_expiry > 0,
                    "version": version,
                    "cipher_suite": cipher[0] if cipher else None,
                    "grade": grade,
                    "san_names": san_names,
                    "san_ips": san_ips,
                    "signature_algorithm": cert.get('signatureAlgorithm', 'Unknown'),
                    "weak_flags": flags,
                    "chain": chain_info,
                },
                "scanner": "ssl"
            }
            
            return result
            
        except ssl.SSLCertVerificationError as e:
            return {
                "success": True,
                "target": target,
                "certificate": None,
                "error": f"SSL verification failed: {str(e)}",
                "is_valid": False,
                "scanner": "ssl"
            }
        except socket.timeout:
            return self._format_error(Exception("Connection timed out"))
        except ConnectionRefusedError:
            return self._format_error(Exception("Connection refused"))
        except Exception as e:
            return self._format_error(e)
    
    def _weak_flags(self, version: Optional[str], cipher: Optional[Tuple[str, ...]]) -> List[str]:
        """Return human-readable weak protocol/cipher flags for the negotiated session."""
        flags: List[str] = []
        if version in _WEAK_PROTOCOLS:
            flags.append(f"weak-protocol:{version}")
        if cipher:
            name = cipher[0]
            for marker in _WEAK_CIPHER_MARKERS:
                if marker in name:
                    flags.append(f"weak-cipher:{marker}")
        return flags

    def _analyze_chain(self, der_certs: List[bytes]) -> Dict[str, Any]:
        """Walk the presented certificate chain (leaf -> intermediates)."""
        parsed = []
        for der in der_certs:
            try:
                c = x509.load_der_x509_certificate(der)
            except Exception:
                continue
            pub = c.public_key()
            key_bits = None
            key_type = type(pub).__name__
            if isinstance(pub, rsa.RSAPublicKey):
                key_bits = pub.key_size
            elif isinstance(pub, (ec.ECPublicKey,)):
                key_bits = pub.key_size
            parsed.append({
                "subject": c.subject.rfc4514_string(),
                "issuer": c.issuer.rfc4514_string(),
                "not_after": c.not_valid_after_utc.isoformat(),
                "key_type": key_type,
                "key_bits": key_bits,
                "signature_algorithm": c.signature_hash_algorithm.name
                if c.signature_hash_algorithm else "unknown",
            })
        # A complete chain presents >= 2 certs (leaf + >=1 intermediate) or is
        # self-signed (1). If the server only sent the leaf, the chain is incomplete.
        complete = len(parsed) >= 2 or (len(parsed) == 1 and parsed[0]["subject"] == parsed[0]["issuer"])
        return {
            "depth": len(parsed),
            "complete": complete,
            "certs": parsed,
        }

    def _calculate_grade(
        self, 
        cert: dict, 
        version: Optional[str], 
        cipher: Optional[Tuple[str, ...]],
        days_until_expiry: int,
        flags: Optional[List[str]] = None
    ) -> str:
        """Calculate SSL grade (A+ to F)."""
        score = 100
        
        # Penalize old protocols
        if version == 'TLSv1':
            score -= 40
        elif version == 'TLSv1.1':
            score -= 30
        
        # Penalize weak ciphers
        if cipher and 'RC4' in cipher[0]:
            score -= 20
        if cipher and 'DES' in cipher[0]:
            score -= 20
        if cipher and 'NULL' in cipher[0]:
            score -= 50
        
        # Penalize any weak flags surfaced by the negotiated session
        if flags:
            score -= 25
        
        # Penalize expired or near-expiry
        if days_until_expiry < 0:
            score -= 50
        elif days_until_expiry < 30:
            score -= 20
        elif days_until_expiry < 90:
            score -= 10
        
        # Check key length
        subject = dict(x[0] for x in cert.get('subject', []))
        
        # Convert score to grade
        if score >= 90:
            return 'A+'
        elif score >= 80:
            return 'A'
        elif score >= 70:
            return 'B'
        elif score >= 60:
            return 'C'
        elif score >= 50:
            return 'D'
        else:
            return 'F'
