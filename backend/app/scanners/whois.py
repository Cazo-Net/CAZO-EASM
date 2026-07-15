import whois
from typing import Any, Dict
from app.scanners.base import BaseScanner
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class WhoisScanner(BaseScanner):
    """Scanner for WHOIS lookups using python-whois."""
    
    def validate_target(self, target: str) -> bool:
        """Validate domain format."""
        import re
        domain_regex = re.compile(
            r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        )
        return bool(domain_regex.match(target))
    
    async def scan(self, target: str, **kwargs) -> Dict[str, Any]:
        """Perform WHOIS lookup."""
        if not self.validate_target(target):
            return self._format_error(ValueError(f"Invalid domain: {target}"))
        
        try:
            # python-whois is synchronous, run in executor
            loop = __import__('asyncio').get_event_loop()
            w = await loop.run_in_executor(None, whois.whois, target)
            
            if w is None:
                return {
                    "success": True,
                    "target": target,
                    "data": None,
                    "error": "No WHOIS data available",
                    "scanner": "python-whois"
                }
            
            # Parse expiration date
            expiration_date = None
            if w.expiration_date:
                if isinstance(w.expiration_date, list):
                    expiration_date = w.expiration_date[0]
                else:
                    expiration_date = w.expiration_date
            
            # Parse creation date
            creation_date = None
            if w.creation_date:
                if isinstance(w.creation_date, list):
                    creation_date = w.creation_date[0]
                else:
                    creation_date = w.creation_date
            
            # Parse name servers
            name_servers = []
            if w.name_servers:
                if isinstance(w.name_servers, list):
                    name_servers = [ns.lower() for ns in w.name_servers]
                else:
                    name_servers = [str(w.name_servers).lower()]
            
            result = {
                "success": True,
                "target": target,
                "data": {
                    "registrar": w.registrar,
                    "creation_date": creation_date.isoformat() if isinstance(creation_date, datetime) else str(creation_date) if creation_date else None,
                    "expiration_date": expiration_date.isoformat() if isinstance(expiration_date, datetime) else str(expiration_date) if expiration_date else None,
                    "updated_date": w.updated_date.isoformat() if isinstance(w.updated_date, datetime) else str(w.updated_date) if w.updated_date else None,
                    "name_servers": name_servers,
                    "registrant_name": w.name,
                    "registrant_org": w.org,
                    "registrant_country": w.country,
                    "emails": w.emails if hasattr(w, 'emails') else [],
                    "dnssec": w.dnssec if hasattr(w, 'dnssec') else None,
                    "status": w.status if hasattr(w, 'status') else [],
                },
                "scanner": "python-whois"
            }
            
            # Add domain status parsing
            if hasattr(w, 'status') and w.status:
                if isinstance(w.status, list):
                    result["data"]["statuses"] = w.status
                else:
                    result["data"]["statuses"] = [str(w.status)]
            
            return result
            
        except whois.parser.PywhoisError as e:
            return {
                "success": True,
                "target": target,
                "data": None,
                "error": f"WHOIS lookup failed: {str(e)}",
                "scanner": "python-whois"
            }
        except Exception as e:
            return self._format_error(e)
