import dns.resolver
import dns.query
import dns.zone
import dns.rdatatype
import dns.name
import asyncio
from typing import Any, Dict, List
from app.scanners.base import BaseScanner
from app.scanners.registry import register_scanner, ScannerCategory
import logging

logger = logging.getLogger(__name__)


@register_scanner(
    name="zone-transfer",
    category=ScannerCategory.DNS,
    description="DNS zone transfer (AXFR) attempt against nameservers.",
)
class ZoneTransferScanner(BaseScanner):
    
    TRANSFER_RDTYPES = ['A', 'AAAA', 'CNAME', 'MX', 'TXT']
    
    def validate_target(self, target: str) -> bool:
        import re
        hostname_regex = re.compile(
            r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        )
        return bool(hostname_regex.match(target))
    
    async def _attempt_transfer(self, ns_ip: str, target: str) -> dns.zone.Zone:
        def _do_transfer():
            nameserver = ns_ip
            timeout = 5
            try:
                transfer = dns.query.xfr(
                    nameserver,
                    target,
                    lifetime=timeout,
                    one_rr_per_rrset=False,
                )
                return dns.zone.from_xfr(transfer, relativize=False)
            except dns.query.TransferError:
                raise
            except Exception:
                raise
        
        return await asyncio.to_thread(_do_transfer)
    
    async def _get_ns_ips(self, target: str) -> List[str]:
        ns_ips = []
        try:
            import dns.resolver as _resolver
            def _resolve_ns():
                answers = _resolver.resolve(target, 'NS')
                return [str(rdata).rstrip('.') for rdata in answers]
            ns_hostnames = await asyncio.to_thread(_resolve_ns)
            
            async def _resolve_a(ns_host):
                try:
                    def _do_resolve():
                        return [str(rdata) for rdata in _resolver.resolve(ns_host, 'A')]
                    return await asyncio.to_thread(_do_resolve)
                except Exception:
                    return []
            
            a_results = await asyncio.gather(*[_resolve_a(ns) for ns in ns_hostnames], return_exceptions=True)
            for ips in a_results:
                if isinstance(ips, list):
                    ns_ips.extend(ips)
        except Exception as e:
            logger.warning(f"Failed to query NS records for {target}: {e}")
        
        return ns_ips
    
    def _extract_records(self, zone: dns.zone.Zone, target: str) -> Dict[str, Dict[str, List[str]]]:
        records: Dict[str, Dict[str, List[str]]] = {}
        
        for name, node in zone.nodes.items():
            hostname = str(name).rstrip('.')
            if hostname == '@' or hostname == target.rstrip('.'):
                hostname = target
            
            for rdataset in node.rdatasets:
                rdtype = dns.rdatatype.to_text(rdataset.rdtype)
                if rdtype not in self.TRANSFER_RDTYPES:
                    continue
                
                if hostname not in records:
                    records[hostname] = {}
                
                if rdtype not in records[hostname]:
                    records[hostname][rdtype] = []
                
                for rdata in rdataset:
                    if rdtype == 'A':
                        records[hostname][rdtype].append(str(rdata))
                    elif rdtype == 'AAAA':
                        records[hostname][rdtype].append(str(rdata))
                    elif rdtype == 'CNAME':
                        records[hostname][rdtype].append(str(rdata.target).rstrip('.'))
                    elif rdtype == 'MX':
                        records[hostname][rdtype].append(str(rdata.exchange).rstrip('.'))
                    elif rdtype == 'TXT':
                        records[hostname][rdtype].append(str(rdata))
        
        return records
    
    async def scan(self, target: str, **kwargs) -> Dict[str, Any]:
        if not self.validate_target(target):
            return self._format_error(ValueError(f"Invalid hostname: {target}"))
        
        ns_ips = await self._get_ns_ips(target)
        
        if not ns_ips:
            return {
                "success": True,
                "target": target,
                "transfer_success": False,
                "nameservers": [],
                "records": {},
                "subdomains": [],
                "scanner": "zone-transfer",
            }
        
        all_records: Dict[str, Dict[str, List[str]]] = {}
        transfer_success = False
        
        for ns_ip in ns_ips:
            try:
                zone = await asyncio.wait_for(
                    self._attempt_transfer(ns_ip, target),
                    timeout=5,
                )
                records = self._extract_records(zone, target)
                
                for hostname, rdtype_map in records.items():
                    if hostname not in all_records:
                        all_records[hostname] = {}
                    for rdtype, values in rdtype_map.items():
                        if rdtype not in all_records[hostname]:
                            all_records[hostname][rdtype] = []
                        all_records[hostname][rdtype].extend(values)
                
                transfer_success = True
                logger.info(f"Zone transfer successful against {ns_ip}")
                break
            
            except asyncio.TimeoutError:
                logger.debug(f"Zone transfer timed out for {ns_ip}")
            except dns.query.TransferError as e:
                logger.debug(f"Zone transfer refused by {ns_ip}: {e}")
            except Exception as e:
                logger.debug(f"Zone transfer failed for {ns_ip}: {e}")
        
        subdomains = sorted(set(all_records.keys()))
        
        return {
            "success": True,
            "target": target,
            "transfer_success": transfer_success,
            "nameservers": ns_ips,
            "records": all_records,
            "subdomains": subdomains,
            "scanner": "zone-transfer",
        }
