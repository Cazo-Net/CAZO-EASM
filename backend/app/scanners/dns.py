import asyncio
import dns.resolver
import dns.rdatatype
import dns.exception
from typing import Any, Dict
from app.scanners.base import BaseScanner
from app.scanners.registry import register_scanner, ScannerCategory
import logging

logger = logging.getLogger(__name__)


def _resolve_sync(target: str, record_type: str):
    """Synchronous DNS resolve — runs in a thread."""
    return dns.resolver.resolve(target, record_type)


def _resolve_dmarc_sync(target: str):
    return dns.resolver.resolve(f'_dmarc.{target}', 'TXT')


def _resolve_dkim_sync(fqdn: str):
    return dns.resolver.resolve(fqdn, 'TXT')


@register_scanner(
    name="dns",
    category=ScannerCategory.DNS,
    description="DNS record analysis (A/AAAA/CNAME/MX/TXT/NS) via dnspython.",
)
class DNSScanner(BaseScanner):
    """Scanner for DNS record analysis using dnspython."""

    RECORD_TYPES = ['A', 'AAAA', 'MX', 'NS', 'TXT', 'CNAME', 'SOA', 'SRV']

    DMARC_SELECTORS = ['default', '_dmarc']
    DKIM_SELECTORS = ['default', 'selector1', 'selector2', 'google', 'k1', 'mandrill', 'everlytickey1', 'dkim', 's1', 's2']

    def validate_target(self, target: str) -> bool:
        import re
        hostname_regex = re.compile(
            r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        )
        return bool(hostname_regex.match(target))

    async def _query_one(self, target: str, record_type: str):
        """Query a single record type in a thread."""
        try:
            answers = await asyncio.wait_for(
                asyncio.to_thread(_resolve_sync, target, record_type),
                timeout=3,
            )
            rrset_ttl = int(answers.ttl) if getattr(answers, "ttl", None) is not None else None
            records = []
            ips = []
            for rdata in answers:
                record = {"type": record_type}
                rdata_ttl = getattr(rdata, "ttl", None)
                record["ttl"] = int(rdata_ttl) if rdata_ttl is not None else rrset_ttl

                if record_type == 'A':
                    record["value"] = str(rdata)
                    ips.append(str(rdata))
                elif record_type == 'AAAA':
                    record["value"] = str(rdata)
                    ips.append(str(rdata))
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
            return record_type, records, ips, None
        except dns.resolver.NoAnswer:
            return record_type, [], [], None
        except dns.resolver.NXDOMAIN:
            return record_type, [], [], "NXDOMAIN"
        except dns.resolver.NoNameservers:
            return record_type, [], [], f"No nameservers for {target} ({record_type})"
        except dns.resolver.NoRootServers:
            return record_type, [], [], f"No root servers reachable for {target}"
        except (dns.exception.Timeout, asyncio.TimeoutError, TimeoutError):
            return record_type, [], [], f"DNS query timed out for {target} ({record_type})"
        except Exception as e:
            return record_type, [], [], f"DNS error: {type(e).__name__}: {e}"

    async def scan(self, target: str, **kwargs) -> Dict[str, Any]:
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

            # Parallel: all record types at once
            tasks = [self._query_one(target, rt) for rt in self.RECORD_TYPES]
            dmarc_task = asyncio.to_thread(_resolve_dmarc_sync, target)
            dkim_tasks = [
                asyncio.to_thread(_resolve_dkim_sync, f'{sel}._domainkey.{target}')
                for sel in self.DKIM_SELECTORS
            ]

            all_results = await asyncio.gather(*tasks, return_exceptions=True)
            all_ips = []
            failed = False
            failure_reason = None

            for item in all_results:
                if isinstance(item, Exception):
                    failed = True
                    failure_reason = str(item)
                    continue
                rt, records, ips, err = item
                if records:
                    results["records"][rt] = records
                all_ips.extend(ips)
                if err:
                    if "NXDOMAIN" in str(err):
                        return {
                            "success": True,
                            "target": target,
                            "records": {},
                            "ips": [],
                            "error": "Domain does not exist",
                            "status": "not_applicable",
                            "scanner": "dnspython"
                        }
                    failed = True
                    failure_reason = failure_reason or err

            results["ips"] = sorted(set(all_ips))

            # DMARC (in thread)
            try:
                dmarc_answers = await asyncio.wait_for(dmarc_task, timeout=3)
                dmarc_ttl = int(dmarc_answers.ttl) if getattr(dmarc_answers, "ttl", None) is not None else None
                for rdata in dmarc_answers:
                    results["records"]["DMARC"] = [{"type": "DMARC", "value": str(rdata), "ttl": dmarc_ttl}]
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers,
                    dns.resolver.NoRootServers, dns.exception.Timeout, asyncio.TimeoutError, TimeoutError):
                pass
            except Exception:
                pass

            # DKIM (parallel in threads)
            dkim_results = await asyncio.gather(*dkim_tasks, return_exceptions=True)
            for sel, item in zip(self.DKIM_SELECTORS, dkim_results):
                if isinstance(item, Exception):
                    continue
                try:
                    dkim_ttl = int(item.ttl) if getattr(item, "ttl", None) is not None else None
                    for rdata in item:
                        results["records"][f"DKIM_{sel}"] = [{"type": "DKIM", "value": str(rdata), "selector": sel, "ttl": dkim_ttl}]
                except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers,
                        dns.resolver.NoRootServers, dns.exception.Timeout, asyncio.TimeoutError):
                    pass

            if not results["records"] and failed:
                if failure_reason and "timed out" in str(failure_reason).lower():
                    results["status"] = "blocked_by_cdn"
                else:
                    results["status"] = "resolution_failed"
                results["error"] = failure_reason
            elif not results["records"]:
                results["status"] = "no_records"
            else:
                results["status"] = "ok"

            return results

        except Exception as e:
            return self._format_error(e)

    async def resolve_ip(self, ip: str) -> Dict[str, Any]:
        try:
            def _reverse():
                result = dns.reversename.from_address(ip)
                return dns.resolver.resolve(result, 'PTR')
            answers = await asyncio.wait_for(asyncio.to_thread(_reverse), timeout=3)
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
