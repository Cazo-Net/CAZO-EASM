import dns.resolver
import dns.rdatatype
from typing import Any, Dict, List
from app.scanners.base import BaseScanner
import logging

logger = logging.getLogger(__name__)


class DNSScanner(BaseScanner):
    """Scanner for DNS record analysis using dnspython."""
    
    RECORD_TYPES = ['A', 'AAAA', 'MX', 'NS', 'TXT', 'CNAME', 'SOA', 'SRV']
    
    def validate_target(self, target: str) -> bool:
        """Validate hostname format."""
        import re
        hostname_regex = re.compile(
            r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        )
        return bool(hostname_regex.match(target))
    
    async def scan(self, target: str, **kwargs) -> Dict[str, Any]:
        """Perform DNS lookup for all record types."""
        if not self.validate_target(target):
            return self._format_error(ValueError(f"Invalid hostname: {target}"))
        
        try:
            results = {
                "success": True,
                "target": target,
                "records": {},
                "ips": [],
                "scanner": "dnspython"
            }
            
            # Query each record type
            for record_type in self.RECORD_TYPES:
                try:
                    answers = dns.resolver.resolve(target, record_type)
                    records = []
                    
                    for rdata in answers:
                        record = {"type": record_type}
                        
                        if record_type == 'A':
                            record["value"] = str(rdata)
                            results["ips"].append(str(rdata))
                        elif record_type == 'AAAA':
                            record["value"] = str(rdata)
                            results["ips"].append(str(rdata))
                        elif record_type == 'MX':
                            record["value"] = str(rdata.exchange)
                            record["priority"] = rdata.preference
                        elif record_type == 'NS':
                            record["value"] = str(rdata)
                        elif record_type == 'TXT':
                            record["value"] = str(rdata)
                        elif record_type == 'CNAME':
                            record["value"] = str(rdata)
                        elif record_type == 'SOA':
                            record["value"] = {
                                "mname": str(rdata.mname),
                                "rname": str(rdata.rname),
                                "serial": rdata.serial
                            }
                        elif record_type == 'SRV':
                            record["value"] = {
                                "target": str(rdata.target),
                                "port": rdata.port,
                                "priority": rdata.priority,
                                "weight": rdata.weight
                            }
                        
                        records.append(record)
                    
                    if records:
                        results["records"][record_type] = records
                        
                except dns.resolver.NoAnswer:
                    pass
                except dns.resolver.NXDOMAIN:
                    return {
                        "success": True,
                        "target": target,
                        "records": {},
                        "ips": [],
                        "error": "Domain does not exist",
                        "scanner": "dnspython"
                    }
                except dns.resolver.NoNameservers:
                    logger.warning(f"No nameservers for {target} record type {record_type}")
                except Exception as e:
                    logger.warning(f"Error querying {record_type}: {e}")
            
            # Remove duplicate IPs
            results["ips"] = sorted(list(set(results["ips"])))
            
            return results
            
        except Exception as e:
            return self._format_error(e)
    
    async def resolve_ip(self, ip: str) -> Dict[str, Any]:
        """Reverse DNS lookup."""
        try:
            result = dns.reversename.from_address(ip)
            answers = dns.resolver.resolve(result, 'PTR')
            
            return {
                "success": True,
                "ip": ip,
                "hostnames": [str(rdata) for rdata in answers],
                "scanner": "dnspython"
            }
        except Exception as e:
            return {
                "success": False,
                "ip": ip,
                "error": str(e),
                "scanner": "dnspython"
            }
