import ssl
import socket
from typing import Any, Dict
from app.scanners.base import BaseScanner
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


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
            # Create SSL context
            context = ssl.create_default_context()
            
            # Connect and get certificate
            with socket.create_connection((target, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=target) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()
            
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
            
            # Calculate grade
            grade = self._calculate_grade(cert, version, cipher, days_until_expiry)
            
            # Get SANs
            san_names = []
            san_ips = []
            if 'subjectAltName' in cert:
                for san_type, san_value in cert['subjectAltName']:
                    if san_type == 'DNS':
                        san_names.append(san_value)
                    elif san_type == 'IP Address':
                        san_ips.append(san_value)
            
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
    
    def _calculate_grade(
        self, 
        cert: dict, 
        version: str, 
        cipher: tuple,
        days_until_expiry: int
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
