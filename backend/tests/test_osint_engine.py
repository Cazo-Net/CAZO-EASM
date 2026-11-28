"""OSINT lookup engine: passive, sourced, no invented results.

Third-party APIs and DNS are faked with responses shaped like the real
services (crt.sh, Cert Spotter, Shodan InternetDB/CVEDB, RDAP, ipinfo,
GreyNoise, AbuseIPDB, HackerTarget, OTX, Wayback).
"""
import json
import socket
from urllib.parse import urlparse

import dns.resolver
import pytest

from app.services import osint

DOMAIN = "acme.com"

CRTSH = [
    {"id": 111, "issuer_name": "C=US, O=Let's Encrypt, CN=R11", "common_name": "acme.com",
     "name_value": "acme.com\nwww.acme.com", "not_before": "2026-10-01T00:00:00",
     "not_after": "2026-12-30T00:00:00", "serial_number": "04aa"},
    {"id": 110, "issuer_name": "C=US, O=Let's Encrypt, CN=R11", "common_name": "vpn.acme.com",
     "name_value": "vpn.acme.com\n*.dev.acme.com", "not_before": "2026-09-01T00:00:00",
     "not_after": "2026-11-30T00:00:00", "serial_number": "03bb"},
    # Substring look-alike: must NOT be treated as a subdomain of acme.com.
    {"id": 109, "issuer_name": "x", "common_name": "notacme.com", "name_value": "notacme.com",
     "not_before": "2026-01-01T00:00:00", "not_after": "2026-04-01T00:00:00", "serial_number": "01"},
]
CERTSPOTTER = [{"id": "1", "dns_names": ["acme.com", "api.acme.com"], "not_before": "2026-10-01T00:00:00Z",
                "not_after": "2026-12-30T00:00:00Z", "cert_sha256": "ab" * 32, "issuer": {"name": "R11"}}]
INTERNETDB = {
    "93.184.215.10": {"ip": "93.184.215.10", "ports": [443, 3389], "hostnames": ["vpn.acme.com"],
                      "cpes": ["cpe:/a:fortinet:fortios:7.0.1", "cpe:/a:openbsd:openssh:8.2"],
                      "tags": [], "vulns": ["CVE-2024-21762", "CVE-2023-0001"]},
}
CVEDB = {
    "CVE-2024-21762": {"cve_id": "CVE-2024-21762", "summary": "FortiOS out-of-bound write in sslvpnd.",
                       "cvss": 9.8, "cvss_v3": 9.8, "epss": 0.94, "kev": True,
                       "published_time": "2024-02-09T09:15:08"},
    "CVE-2023-0001": {"cve_id": "CVE-2023-0001", "summary": "Minor issue.", "cvss": 5.3,
                      "cvss_v3": 5.3, "epss": 0.01, "kev": False, "published_time": "2023-01-01T00:00:00"},
}
RDAP = {
    "ldhName": "ACME.COM", "handle": "123_DOMAIN_COM-VRSN", "status": ["client transfer prohibited"],
    "events": [{"eventAction": "registration", "eventDate": "1991-01-01T05:00:00Z"},
               {"eventAction": "expiration", "eventDate": "2030-01-01T05:00:00Z"}],
    "nameservers": [{"ldhName": "NS1.ACME.COM"}],
    "secureDNS": {"delegationSigned": False},
    "links": [{"rel": "self", "href": "https://rdap.verisign.com/com/v1/domain/ACME.COM"}],
    "entities": [{
        "roles": ["registrar"], "handle": "292",
        "publicIds": [{"type": "IANA Registrar ID", "identifier": "292"}],
        "vcardArray": ["vcard", [["version", {}, "text", "4.0"], ["fn", {}, "text", "MarkMonitor Inc."]]],
        "entities": [{"roles": ["abuse"], "vcardArray": ["vcard", [
            ["fn", {}, "text", ""], ["email", {}, "text", "abusecomplaints@markmonitor.com"]]]}],
    }],
}

DNS = {
    ("acme.com", "A"): ["93.184.215.10"],
    ("acme.com", "NS"): ["ns1.acme.com."],
    ("acme.com", "MX"): ["10 mail.acme.com."],
    ("acme.com", "TXT"): ['"v=spf1 include:_spf.google.com ~all"'],
    ("www.acme.com", "A"): ["93.184.215.10"],
    ("vpn.acme.com", "A"): ["93.184.215.10"],
    ("api.acme.com", "CNAME"): ["acme.cdn.cloudflare.net."],
    ("api.acme.com", "A"): ["104.16.1.1"],
    # dev.acme.com no longer resolves; the stale third-party IP must not be enriched.
    ("_dmarc.acme.com", "TXT"): ['"v=DMARC1; p=none; rua=mailto:d@acme.com"'],
}


class _Resp:
    def __init__(self, status=200, data=None, text=None, url=""):
        self.status_code = status
        self._data = data
        self.text = text if text is not None else (json.dumps(data) if data is not None else "")
        self.content = self.text.encode()
        self.url = url

    def json(self):
        return self._data if self._data is not None else json.loads(self.text or "null")


class _RR:
    def __init__(self, text):
        self._t = text
        if text.split()[0].isdigit() and len(text.split()) == 2:
            self.preference, ex = text.split()
            self.exchange = dns.name.from_text(ex)

    def to_text(self):
        return self._t


@pytest.fixture
def fake_net(monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None, allow_redirects=True, **kw):
        calls.append({"url": url, "params": params, "headers": headers or {}})
        host = urlparse(url).hostname
        path = urlparse(url).path
        if host == "crt.sh":
            return _Resp(data=CRTSH)
        if host == "api.certspotter.com":
            return _Resp(data=CERTSPOTTER)
        if host == "api.hackertarget.com" and "hostsearch" in path:
            return _Resp(text="vpn.acme.com,93.184.215.10\ndev.acme.com,203.0.113.9\nnotacme.com,1.2.3.4")
        if host == "api.hackertarget.com" and "reverseip" in path:
            return _Resp(text="acme.com\nacme-partner.net\nunrelated-shop.org")
        if host == "otx.alienvault.com":
            return _Resp(data={"passive_dns": [{"hostname": "mail.acme.com", "address": "93.184.215.20"}]})
        if host == "rapiddns.io":
            return _Resp(text="<td>old.acme.com</td>")
        if host == "web.archive.org":
            return _Resp(data=[["original"], ["http://legacy.acme.com/login"], ["https://acme.com.evil.net/"]])
        if host == "rdap.org":
            return _Resp(data=RDAP, url="https://rdap.verisign.com/com/v1/domain/acme.com")
        if host == "internetdb.shodan.io":
            ip = path.strip("/")
            return _Resp(data=INTERNETDB[ip]) if ip in INTERNETDB else _Resp(404, {"detail": "No information available"})
        if host == "cvedb.shodan.io":
            cve = path.rsplit("/", 1)[-1]
            return _Resp(data=CVEDB[cve]) if cve in CVEDB else _Resp(404, {})
        if host == "ipinfo.io":
            ip = path.split("/")[1]
            org = "AS13335 Cloudflare, Inc." if ip.startswith("104.16.") else "AS15133 Edgecast Inc."
            return _Resp(data={"ip": ip, "country": "US", "city": "Los Angeles", "org": org})
        if host == "api.greynoise.io":
            return _Resp(404, {"ip": path.rsplit("/", 1)[-1], "noise": False, "riot": False,
                               "message": "IP not observed scanning the internet or contained in RIOT data set."})
        if host == "api.abuseipdb.com":
            return _Resp(data={"data": {"abuseConfidenceScore": 0, "totalReports": 0, "usageType": "Content Delivery Network"}})
        raise AssertionError(f"unexpected request to {url}")

    def fake_resolve(name, rtype, lifetime=None, **kw):
        key = (str(name).rstrip(".").lower(), rtype)
        if key not in DNS:
            raise dns.resolver.NXDOMAIN()
        return [_RR(v) for v in DNS[key]]

    def no_sockets(*a, **kw):
        raise AssertionError(f"passive lookup opened a socket: {a}")

    monkeypatch.setattr(osint.requests, "get", fake_get)
    monkeypatch.setattr(dns.resolver, "resolve", fake_resolve)
    monkeypatch.setattr(socket, "create_connection", no_sockets)
    from app.config import settings
    for k in ("ABUSEIPDB_API_KEY", "GREYNOISE_API_KEY", "OTX_API_KEY", "IPINFO_TOKEN"):
        monkeypatch.setattr(settings, k, "", raising=False)
    return calls


def _lookup():
    return osint.intel_to_dict(osint.lookup_domain(DOMAIN))


def test_lookup_is_passive_and_never_contacts_the_target(fake_net):
    res = _lookup()
    assert res["passive"] is True
    contacted = {urlparse(c["url"]).hostname for c in fake_net}
    assert not any(h == DOMAIN or h.endswith("." + DOMAIN) for h in contacted)
    # No live-check results at all.
    assert res["security_headers"] is None and res["sensitive_paths"] == [] and res["web_fingerprint"] is None
    assert not any(s["passive"] is False for s in res["sources"])


def test_subdomains_merge_sources_and_reject_substring_lookalikes(fake_net):
    res = _lookup()
    hosts = {s["hostname"]: s for s in res["subdomains"]}
    assert {"acme.com", "www.acme.com", "vpn.acme.com", "dev.acme.com", "api.acme.com",
            "mail.acme.com", "old.acme.com"} <= set(hosts)
    assert "notacme.com" not in hosts
    assert set(hosts["vpn.acme.com"]["sources"]) == {"crtsh", "hackertarget"}
    assert hosts["vpn.acme.com"]["source_links"]["crtsh"] == "https://crt.sh/?q=%25.acme.com"
    assert hosts["api.acme.com"]["cname"] == "acme.cdn.cloudflare.net"
    # Stale third-party IP dropped when the name no longer resolves.
    assert hosts["dev.acme.com"]["ips"] == []
    assert res["historical_subdomains"] == ["legacy.acme.com"]


def test_cves_come_from_shodan_with_kev_epss_and_are_marked_potential(fake_net):
    res = _lookup()
    urls = [c["url"] for c in fake_net]
    assert not any("nvd.nist.gov" in u for u in urls), "no keyword NVD searches"
    vulns = res["vulnerabilities"]
    assert [v["cve_id"] for v in vulns] == ["CVE-2024-21762", "CVE-2023-0001"]
    top = vulns[0]
    assert top["is_kev"] and top["cvss"] == 9.8 and top["severity"] == "CRITICAL" and top["epss"] == 0.94
    assert top["confidence"] == "potential" and top["ips"] == ["93.184.215.10"]
    assert top["source_url"] == "https://internetdb.shodan.io/93.184.215.10"
    # Only IPs that resolve now are enriched (not the stale 203.0.113.9).
    assert not any("203.0.113.9" in u for u in urls)


def test_ports_and_technologies_from_internetdb(fake_net):
    res = _lookup()
    ports = {(p["ip"], p["port"]): p for p in res["ports"]}
    assert set(ports) == {("93.184.215.10", 443), ("93.184.215.10", 3389)}
    assert ports[("93.184.215.10", 3389)]["service"] == "RDP"
    assert "vpn.acme.com" in ports[("93.184.215.10", 443)]["hostnames"]
    techs = {t["name"]: t for t in res["technology_details"]}
    assert techs["fortios"]["version"] == "7.0.1" and techs["fortios"]["vendor"] == "fortinet"
    assert "openssh" in res["technologies"]


def test_certificates_from_ct_with_links(fake_net):
    res = _lookup()
    certs = res["certificates"]
    assert certs[0]["source"] == "crtsh" and certs[0]["source_url"] == "https://crt.sh/?id=111"
    assert certs[0]["serial"] == "04AA" and "www.acme.com" in certs[0]["san"]
    assert [c["serial"] for c in certs] == ["04AA", "03BB"], "certs for other domains are dropped"


def test_rdap_parses_registrar_abuse_contact_and_dnssec(fake_net):
    w = _lookup()["whois"]
    assert w["registrar"] == "MarkMonitor Inc."
    assert w["registrar_iana_id"] == "292"
    assert w["abuse_email"] == "abusecomplaints@markmonitor.com"
    assert w["dnssec"] is False and w["name"] == "acme.com"
    assert w["source_url"] == "https://rdap.verisign.com/com/v1/domain/ACME.COM"


def test_key_gated_sources_say_needs_key_instead_of_guessing(fake_net):
    res = _lookup()
    assert not any("abuseipdb.com" in c["url"] for c in fake_net)
    src = {s["id"]: s for s in res["sources"]}
    assert src["abuseipdb"]["status"] == "needs_key"
    assert src["abuseipdb"]["key_env"] == "ABUSEIPDB_API_KEY" and src["abuseipdb"]["key_configured"] is False
    assert all(r["abuse_confidence"] is None for r in res["ip_reputation"])
    # Every passive source has a link a person can open.
    assert all(s["link"] for s in res["sources"] if s["passive"])


def test_abuseipdb_used_when_key_configured(fake_net, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "ABUSEIPDB_API_KEY", "k123", raising=False)
    res = _lookup()
    calls = [c for c in fake_net if "abuseipdb.com" in c["url"]]
    assert calls and calls[0]["headers"].get("Key") == "k123"
    assert {s["id"]: s for s in res["sources"]}["abuseipdb"]["status"] == "ok"
    assert res["ip_reputation"][0]["links"]["abuseipdb"].startswith("https://www.abuseipdb.com/check/")


def test_cdn_detected_passively_and_reverse_ip_skips_cdn_ips(fake_net):
    res = _lookup()
    assert res["waf_cdn"]["cdn"] == "Cloudflare"
    rev_calls = [c for c in fake_net if "reverseiplookup" in c["url"]]
    assert all(c["params"]["q"] != "104.16.1.1" for c in rev_calls)
    co = {c["domain"]: c for c in res["cohosted_domains"]}
    assert co["acme-partner.net"]["same_domain"] is False and co["acme.com"]["same_domain"] is True
    assert co["acme-partner.net"]["source_url"].startswith("https://hackertarget.com/")


def test_risk_score_uses_only_sourced_evidence(fake_net):
    risk = _lookup()["risk_score"]
    details = " | ".join(f["detail"] for f in risk["findings"])
    assert any(f["severity"] == "critical" and "CVE-2024-21762" in f["detail"] for f in risk["findings"])
    assert "RDP (3389)" in details
    assert "p=none" in details
    assert "Could not verify SSL" not in details
    assert all(f.get("source") for f in risk["findings"])


def test_round_trip_from_cache_dict(fake_net):
    d = _lookup()
    intel = osint.intel_from_dict(json.loads(json.dumps(d)))
    assert intel.vulnerabilities[0].is_kev and intel.vulnerabilities[0].ips == ["93.184.215.10"]
    assert intel.ports[0].hostnames and intel.certificates[0].source_url


def test_api_ignores_cache_from_older_engine(client, monkeypatch):
    """A result cached by the old engine (with keyword CVEs) must not be served."""
    from tests.conftest import TestingSessionLocal
    from app.models.osint_cache import OsintCache
    from app.api.v1 import osint as api

    db = TestingSessionLocal()
    try:
        db.add(OsintCache(domain="old.example.org", ttl_seconds=3600,
                          result_json=json.dumps({"query": "old.example.org", "vulnerabilities": [{"cve_id": "CVE-1999-0001"}]})))
        db.commit()
        assert api._get_cached("old.example.org", db) is None
        assert db.query(OsintCache).filter_by(domain="old.example.org").first() is None
        db.add(OsintCache(domain="new.example.org", ttl_seconds=3600,
                          result_json=json.dumps({"engine_version": osint.ENGINE_VERSION, "query": "new.example.org"})))
        db.commit()
        assert api._get_cached("new.example.org", db)["query"] == "new.example.org"
    finally:
        db.close()
