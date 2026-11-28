"""Scan depth profiles: how much of an in-scope domain a scan looks at.

Before these profiles existed, every v2 "full" scan quietly overrode the
port list with 10 ports and only fingerprinted the apex domain. A profile
now decides, in one place:

* which TCP ports are checked and on how many hosts,
* how many web services are fingerprinted and checked for exposures,
* how hard the scan may push each host (concurrency and request rate),
* how long the whole pipeline may run (always inside the job timeout the
  durable queue enforces, ``SCAN_TIMEOUT_*_MINUTES``).

Every profile only ever touches hosts that passed the scope gate in
``pipeline._gate_discovered_assets`` (authorized root domain, public IPs).
Nothing here widens *what* may be scanned, only *how thoroughly*.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from app.scanners.v2.fast_port_scanner import TOP_1000_PORTS

# Web and web-admin ports. Used by the quick profile and to decide which
# open ports get an HTTP fingerprint.
WEB_PORTS: List[int] = [
    80, 81, 443, 591, 593, 832, 981, 1010, 1311, 2082, 2083, 2086, 2087, 2095,
    2096, 2480, 3000, 3001, 3002, 3128, 3333, 4000, 4001, 4002, 4100, 4243,
    4443, 4567, 4711, 4712, 4993, 5000, 5001, 5104, 5108, 5280, 5281, 5601,
    5800, 6543, 7000, 7001, 7396, 7443, 7474, 8000, 8001, 8008, 8014, 8042,
    8060, 8069, 8080, 8081, 8083, 8088, 8090, 8091, 8095, 8118, 8123, 8172,
    8181, 8222, 8243, 8280, 8281, 8333, 8337, 8443, 8500, 8834, 8880, 8888,
    8983, 9000, 9001, 9043, 9060, 9080, 9090, 9091, 9200, 9443, 9502, 9800,
    9981, 10000, 10250, 10443, 11371, 12443, 15672, 16080, 17778, 18091,
    18092, 20720, 32000, 55440, 55672,
]

# Services that should almost never face the internet: databases, caches,
# message brokers, remote admin, container/cluster control planes.
SENSITIVE_SERVICE_PORTS: List[int] = [
    21, 22, 23, 25, 53, 69, 110, 111, 135, 137, 139, 143, 161, 389, 445, 465,
    502, 512, 513, 514, 587, 623, 636, 873, 902, 993, 995, 1080, 1099, 1433,
    1434, 1521, 1583, 1723, 1883, 2049, 2181, 2375, 2376, 2379, 2380, 3050,
    3260, 3306, 3389, 3690, 4369, 4848, 5000, 5005, 5432, 5672, 5900, 5901,
    5984, 5985, 5986, 6000, 6379, 6443, 6666, 7199, 7687, 8086, 8291, 8545,
    8883, 9042, 9092, 9100, 9160, 9300, 9418, 10050, 10051, 10255, 11211,
    15672, 25565, 26257, 27017, 27018, 27019, 28015, 28017, 29015, 50000,
    50070, 61616,
]


def _merge(*lists: List[int]) -> List[int]:
    seen: set = set()
    out: List[int] = []
    for lst in lists:
        for p in lst:
            if 0 < p < 65536 and p not in seen:
                seen.add(p)
                out.append(p)
    return out


QUICK_PORTS: List[int] = _merge(
    [80, 443, 8080, 8443, 22, 21, 25, 3389, 3306, 5432, 6379, 27017, 9200],
    [8000, 8888, 9000, 9090, 9443, 10000, 2083, 2087, 5601, 15672],
)

# Standard (~1,300 ports): the most common ports first, then the full web
# and sensitive-service sets, then every well-known port 1-1024.
STANDARD_PORTS: List[int] = _merge(TOP_1000_PORTS, WEB_PORTS, SENSITIVE_SERVICE_PORTS, list(range(1, 1025)))

# Deep (~10,000 ports): standard plus every port up to 10000.
DEEP_PORTS: List[int] = _merge(STANDARD_PORTS, list(range(1025, 10001)))


@dataclass(frozen=True)
class ScanProfile:
    name: str
    ports: List[int] = field(default_factory=list)
    max_port_hosts: int = 10            # hosts that get a TCP port scan
    port_concurrency_per_host: int = 100
    port_host_concurrency: int = 3      # hosts port-scanned at the same time
    port_host_budget_s: float = 60.0    # time budget per host for the port scan
    max_web_targets: int = 20           # web services fingerprinted + exposure-checked
    web_host_parallelism: int = 8       # web hosts checked at the same time
    http_rps_per_ip: float = 40.0       # request ceiling per server address (all names on it)
    http_concurrency_per_host: int = 3
    http_rps_per_host: float = 5.0      # polite request rate per host
    max_requests_per_host: int = 220
    max_js_files: int = 5               # same-origin scripts read for leaked secrets
    exposure_checks: bool = True
    tls_max_endpoints: int = 10
    pipeline_timeout_s: int = 900
    stage_timeouts_s: Dict[str, int] = field(default_factory=dict)

    def to_config(self) -> Dict[str, Any]:
        """Flatten into the dict the pipeline hands to each scanner."""
        cfg = asdict(self)
        cfg["profile"] = cfg.pop("name")
        cfg["top_ports"] = cfg.pop("ports")
        return cfg


PROFILES: Dict[str, ScanProfile] = {
    "quick": ScanProfile(
        name="quick",
        ports=QUICK_PORTS,
        max_port_hosts=5,
        port_concurrency_per_host=50,
        port_host_budget_s=20,
        max_web_targets=5,
        max_requests_per_host=80,
        max_js_files=2,
        tls_max_endpoints=5,
        pipeline_timeout_s=300,
    ),
    "standard": ScanProfile(
        name="standard",
        ports=STANDARD_PORTS,
        max_port_hosts=25,
        port_concurrency_per_host=100,
        port_host_budget_s=60,
        max_web_targets=40,
        web_host_parallelism=16,
        max_requests_per_host=220,
        max_js_files=5,
        tls_max_endpoints=25,
        pipeline_timeout_s=1500,
    ),
    "deep": ScanProfile(
        name="deep",
        ports=DEEP_PORTS,
        max_port_hosts=50,
        port_concurrency_per_host=200,
        port_host_budget_s=180,
        max_web_targets=80,
        web_host_parallelism=24,
        max_requests_per_host=320,
        max_js_files=10,
        tls_max_endpoints=50,
        pipeline_timeout_s=2400,
    ),
}

# Which profile each scan type uses unless the scan options name one.
SCAN_TYPE_PROFILE = {"quick": "quick", "full": "standard", "custom": "standard"}


def resolve_profile(scan_type: str = "full", options: Optional[Dict[str, Any]] = None) -> ScanProfile:
    """Pick a profile from the scan type and an optional ``depth`` option.

    ``options["depth"]`` may be "quick", "standard" or "deep". The overall
    pipeline timeout is capped below the queue's job timeout so the worker,
    not the job reaper, decides when a scan has run too long.
    """
    options = options or {}
    name = str(options.get("depth") or "").lower() or SCAN_TYPE_PROFILE.get(scan_type or "full", "standard")
    profile = PROFILES.get(name, PROFILES["standard"])

    try:
        from app.config import settings
        minutes = (
            settings.SCAN_TIMEOUT_QUICK_MINUTES if profile.name == "quick"
            else settings.SCAN_TIMEOUT_FULL_MINUTES
        )
        cap = max(60, int(minutes) * 60 - 120)  # leave room to store results
        if profile.pipeline_timeout_s > cap:
            from dataclasses import replace
            profile = replace(profile, pipeline_timeout_s=cap)
    except Exception:  # noqa: BLE001 — settings unavailable in some unit tests
        pass
    return profile
