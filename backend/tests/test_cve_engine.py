"""CVE correlation: NVD import, version ranges, banners, on-demand fetch."""
from __future__ import annotations

import asyncio

import pytest

from app.scanners.cve_engine import (
    CveStore, VersionRange, correlate, correlate_scan, ensure_products, parse_nvd_cve,
    software_inventory,
)


def _nvd(cve_id, cpe, sev="HIGH", score=8.1, **rng):
    return {"cve": {
        "id": cve_id, "published": "2021-06-01T00:00:00",
        "descriptions": [{"lang": "en", "value": f"{cve_id} test description"}],
        "metrics": {"cvssMetricV31": [{"cvssData": {"baseSeverity": sev, "baseScore": score}}]},
        "weaknesses": [{"description": [{"value": "CWE-787"}]}],
        "configurations": [{"nodes": [{"cpeMatch": [{"vulnerable": True, "criteria": cpe, **rng}]}]}],
    }}


NGINX = _nvd("CVE-2021-23017", "cpe:2.3:a:f5:nginx:*:*:*:*:*:*:*:*", score=7.7,
             versionStartIncluding="0.6.18", versionEndExcluding="1.20.1")
OPENSSH = _nvd("CVE-2023-38408", "cpe:2.3:a:openbsd:openssh:*:*:*:*:*:*:*:*", sev="CRITICAL", score=9.8,
               versionEndExcluding="9.3")
EXACT = _nvd("CVE-2099-0001", "cpe:2.3:a:f5:nginx:1.18.0:*:*:*:*:*:*:*", sev="MEDIUM", score=5.0)


@pytest.fixture
def store(tmp_path):
    s = CveStore(str(tmp_path / "cve.db"))
    s.add_nvd_items([NGINX, OPENSSH, EXACT])
    return s


def test_parser_reads_vendor_product_and_ranges():
    row, matches = parse_nvd_cve(NGINX)
    assert row["severity"] == "high" and row["base_score"] == 7.7 and row["cwe"] == "CWE-787"
    assert matches == [{"cve_id": "CVE-2021-23017", "vendor": "f5", "product": "nginx", "exact": None,
                        "start_incl": "0.6.18", "start_excl": None, "end_incl": None, "end_excl": "1.20.1"}]


def test_ranges_need_every_bound():
    r = VersionRange(start_incl="0.6.18", end_excl="1.20.1")
    assert r.contains("1.18.0") and r.contains("0.6.18")
    assert not r.contains("1.20.1") and not r.contains("1.24.0") and not r.contains("0.5.0")
    assert not VersionRange().contains("1.0")  # "all versions" is not evidence


def test_match_by_range_and_exact(store):
    ids = {m["cve_id"] for m in store.match("f5", "nginx", "1.18.0")}
    assert ids == {"CVE-2021-23017", "CVE-2099-0001"}
    assert store.match("f5", "nginx", "1.24.0") == []
    assert store.match("apache", "http_server", "1.18.0") == []  # no cross-product matches


def test_banners_from_port_scans_are_correlated(store):
    inv = software_inventory(
        {"www.example.com": [{"name": "nginx", "version": "1.18.0"}]},
        {"ssh.example.com": [{"port": 22, "service": "ssh", "product": "OpenSSH",
                              "version": "8.9p1 Ubuntu 3ubuntu0.6", "banner": "SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.6"}]},
    )
    findings = correlate(store, inv)
    by = {(f["host"], f["cve_id"]): f for f in findings}
    ssh = by[("ssh.example.com", "CVE-2023-38408")]
    assert ssh["severity"] == "critical"
    assert "distro-backport-possible" in ssh["tags"]
    assert any("port 22/ssh" in e for e in ssh["extracted_results"])
    web = by[("www.example.com", "CVE-2021-23017")]
    assert "< 1.20.1" in " ".join(web["extracted_results"])
    assert "unverified" in web["tags"] and "Fix: upgrade nginx" in web["description"]


def test_old_nginx_vendor_name_is_also_searched(tmp_path):
    s = CveStore(str(tmp_path / "c.db"))
    s.add_nvd_items([_nvd("CVE-2013-2028", "cpe:2.3:a:nginx:nginx:*:*:*:*:*:*:*:*",
                          versionStartIncluding="1.3.9", versionEndIncluding="1.4.0")])
    f = correlate(s, [{"host": "h", "name": "nginx", "version": "1.4.0", "seen_on": "web", "banner": ""}])
    assert [x["cve_id"] for x in f] == ["CVE-2013-2028"]


def test_products_are_fetched_once_and_cached(store):
    calls = []

    def fake_fetch(st, vendor, product, deadline):
        calls.append((vendor, product))
        return "ok"

    keys = [("f5", "nginx"), ("openbsd", "openssh")]
    assert set(ensure_products(store, keys, fetch=fake_fetch).values()) == {"ok"}
    assert set(ensure_products(store, keys, fetch=fake_fetch).values()) == {"cached"}
    assert len(calls) == 2


def test_nvd_failure_is_not_cached_and_does_not_fail(store):
    def boom(*a, **k):
        raise ConnectionError("offline")

    st = ensure_products(store, [("f5", "nginx")], fetch=boom)
    assert st["f5:nginx"].startswith("error")
    assert not store.product_synced("f5", "nginx")


def test_correlate_scan_end_to_end_without_network(store, monkeypatch):
    monkeypatch.setenv("CVE_NVD_FETCH", "false")
    findings, status = asyncio.run(correlate_scan(
        {"a.example.com": [{"name": "nginx", "version": "1.18.0"}]}, {}, store=store))
    assert {f["cve_id"] for f in findings} == {"CVE-2021-23017", "CVE-2099-0001"}
    assert status.startswith("ok (2 CVEs")
