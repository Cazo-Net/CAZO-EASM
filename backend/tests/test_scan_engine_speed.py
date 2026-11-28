"""Speed work on both scan engines: shared port scans, stage waves, progress."""
from __future__ import annotations

import asyncio
import time

import dns.resolver
import pytest

from app.scanners.runner import ScanRunner
from app.scanners.v2.pipeline import DEFAULT_STAGE_ORDER, PipelineStage, group_stages


# ── Standard engine: one port scan per set of addresses ─────────────────────

class _FakeDNS:
    def __init__(self, ip_map):
        self.ip_map = ip_map

    async def run_with_retry(self, host, **kw):
        await asyncio.sleep(0.01)
        ips = self.ip_map.get(host, [])
        return {"success": bool(ips), "ips": ips, "records": {"A": ips}}


class _Ok:
    async def run_with_retry(self, host, **kw):
        return {"success": False}


class _FakePorts:
    def __init__(self):
        self.calls = []

    async def run_with_retry(self, host, **kw):
        self.calls.append(host)
        await asyncio.sleep(0.05)
        return {"success": True, "ports": [{"port": 443, "state": "open", "service": "https"}]}


def _runner(ip_map):
    r = ScanRunner()
    r.dns_scanner = _FakeDNS(ip_map)
    r.ssl_scanner = _Ok()
    r.tech_scanner = _Ok()
    r.port_scanner = _FakePorts()
    return r


def test_hosts_on_the_same_addresses_share_one_port_scan():
    ip_map = {f"a{i}.example.com": ["93.184.215.10"] for i in range(6)}
    ip_map.update({"b.example.com": ["93.184.215.20"], "c.example.com": []})
    r = _runner(ip_map)
    cache: dict = {}

    async def go():
        return await asyncio.gather(*[
            r._scan_one_subdomain(h, "quick", None, "example.com", cache) for h in ip_map
        ])

    results = {x["subdomain"]: x for x in asyncio.run(go())}
    # 6 names on one IP -> 1 scan, plus b (own IP) and c (no DNS answer: scanned by name)
    assert len(r.port_scanner.calls) == 3
    shared = [h for h, x in results.items() if x["ports"].get("shared_scan_of")]
    assert len(shared) == 5
    for x in results.values():
        assert x["ports"]["ports"][0]["port"] == 443


def test_shared_results_are_copies_not_the_same_objects():
    ip_map = {"a.example.com": ["93.184.215.10"], "b.example.com": ["93.184.215.10"]}
    r = _runner(ip_map)
    cache: dict = {}

    async def go():
        return await asyncio.gather(*[
            r._scan_one_subdomain(h, "quick", None, "example.com", cache) for h in ip_map
        ])

    a, b = asyncio.run(go())
    a["ports"]["ports"][0]["port"] = 1
    assert b["ports"]["ports"][0]["port"] == 443


def test_without_cache_every_host_is_scanned():
    ip_map = {f"a{i}.example.com": ["93.184.215.10"] for i in range(3)}
    r = _runner(ip_map)

    async def go():
        await asyncio.gather(*[r._scan_one_subdomain(h, "quick", None, "example.com") for h in ip_map])

    asyncio.run(go())
    assert len(r.port_scanner.calls) == 3


# ── Standard engine DNS: a missing DMARC record must not fail the host ──────

def test_dns_scan_survives_hosts_without_dmarc(monkeypatch):
    from app.scanners import dns as dns_mod

    class _RData:
        def __str__(self):
            return "93.184.215.10"

    class _Ans(list):
        ttl = 60

    def fake(target, rtype="A", *a, **k):
        if str(target) != "www.example.com":
            raise dns.resolver.NXDOMAIN()  # _dmarc.www... and the DKIM names
        if rtype == "A":
            return _Ans([_RData()])
        raise dns.resolver.NoAnswer()

    monkeypatch.setattr(dns_mod, "_resolve_sync", lambda t, r: fake(t, r))
    monkeypatch.setattr(dns.resolver, "resolve", fake)
    res = asyncio.run(dns_mod.DNSScanner().scan("www.example.com"))
    assert res["success"] is True
    assert res["ips"] == ["93.184.215.10"]


# ── Scanner v2: stage waves ────────────────────────────────────────────────

def test_default_stages_run_in_six_waves():
    waves = group_stages(DEFAULT_STAGE_ORDER)
    assert waves == [
        [PipelineStage.ASSET_DISCOVERY],
        [PipelineStage.DNS_INTELLIGENCE, PipelineStage.NETWORK_INTELLIGENCE],
        [PipelineStage.TECHNOLOGY_FINGERPRINT, PipelineStage.CERTIFICATE_ANALYSIS, PipelineStage.WEB_EXPOSURE],
        [PipelineStage.VULNERABILITY_ASSESSMENT],
        [PipelineStage.RISK_EVALUATION],
        [PipelineStage.GRAPH_MAPPING],
    ]


def test_waves_can_be_switched_off_and_never_reorder():
    assert all(len(w) == 1 for w in group_stages(DEFAULT_STAGE_ORDER, parallel=False))
    custom = [PipelineStage.WEB_EXPOSURE, PipelineStage.ASSET_DISCOVERY, PipelineStage.CERTIFICATE_ANALYSIS]
    assert [s for w in group_stages(custom) for s in w] == custom
    assert len(group_stages(custom)) == 3


def test_stages_in_a_wave_overlap_in_time(monkeypatch):
    """Two 0.3 s stages of the same wave finish in about 0.3 s, not 0.6 s."""
    from app.scanners.v2 import pipeline as pl
    from app.scanners.v2.pipeline import ScanPipeline, StageResult

    async def slow_stage(self, stage, *a, **k):
        await asyncio.sleep(0.3)
        return StageResult(stage=stage)

    monkeypatch.setattr(pl.ScanPipeline, "_execute_stage", slow_stage)
    monkeypatch.setattr(pl.ScanPipeline, "_stage_kwargs", lambda self, *a, **k: {})
    p = ScanPipeline(stages=[PipelineStage.TECHNOLOGY_FINGERPRINT, PipelineStage.CERTIFICATE_ANALYSIS,
                             PipelineStage.WEB_EXPOSURE])
    start = time.monotonic()
    res = asyncio.run(p.execute("example.com"))
    took = time.monotonic() - start
    assert took < 0.6
    assert list(res.stages) == ["technology_fingerprint", "certificate_analysis", "web_exposure"]


# ── Progress writes ─────────────────────────────────────────────────────────

class _Scan:
    progress = 0


class _DB:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


def test_progress_writer_skips_redundant_writes_and_always_writes_100():
    from app.services.scan_progress import make_progress_writer

    db, scan = _DB(), _Scan()
    cb = make_progress_writer(db, scan, min_interval=60)

    async def go():
        for pct in (5, 5, 10, 20, 30, 100):
            await cb(pct, "x")

    asyncio.run(go())
    assert db.commits == 2  # 5 and 100; the rest fall inside the interval
    assert scan.progress == 100


def test_progress_writer_survives_commit_errors():
    from app.services.scan_progress import make_progress_writer

    class _BadDB(_DB):
        def commit(self):
            raise RuntimeError("db down")

    cb = make_progress_writer(_BadDB(), _Scan(), min_interval=0)
    asyncio.run(cb(50, "x"))  # must not raise


# ── DNS answer cache in the scope guard ────────────────────────────────────

def test_resolve_host_caches_answers(monkeypatch):
    from app.core import target_guard

    calls = []

    def fake(host, timeout):
        calls.append(host)
        return ["93.184.215.10"]

    monkeypatch.setattr(target_guard, "_resolve_host_uncached", fake)
    assert target_guard.resolve_host("A.example.com") == ["93.184.215.10"]
    assert target_guard.resolve_host("a.example.com.") == ["93.184.215.10"]
    assert calls == ["a.example.com"]


# ── Scanner v2 web exposure: names on one server share a politeness limit ───

def test_web_exposure_limits_requests_per_server_address(monkeypatch):
    from app.core import target_guard
    from app.scanners.v2.web_exposure import WebExposureScanner

    monkeypatch.setattr(target_guard, "_resolve_host_uncached", lambda h, t: ["93.184.215.10"])
    sc = WebExposureScanner({"http_rps_per_ip": 1000, "http_concurrency_per_ip": 2})
    in_flight = {"now": 0, "max": 0}

    async def go():
        async def one(host):
            key = await sc._server_key(host)
            async with sc.limiter.slot(host), sc.ip_limiter.slot(key):
                in_flight["now"] += 1
                in_flight["max"] = max(in_flight["max"], in_flight["now"])
                await asyncio.sleep(0.02)
                in_flight["now"] -= 1

        await asyncio.gather(*[one(f"h{i}.example.com") for i in range(10)])

    asyncio.run(go())
    assert {sc._ip_of[f"h{i}.example.com"] for i in range(10)} == {"93.184.215.10"}
    assert in_flight["max"] == 2


def test_profiles_check_more_web_hosts_at_once():
    from app.scanners.v2.profiles import resolve_profile

    assert resolve_profile("full").to_config()["web_host_parallelism"] == 16
    assert resolve_profile("full", {"depth": "deep"}).to_config()["web_host_parallelism"] == 24
    assert resolve_profile("full").to_config()["http_rps_per_ip"] == 40.0
