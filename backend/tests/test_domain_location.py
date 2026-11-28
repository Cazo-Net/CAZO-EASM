"""Domain location: WHOIS registrant country plus hosting location of each IP."""
from datetime import datetime, timezone

import requests

from app.models.asset import Subdomain
from app.models.dns import DNSRecord
from app.models.scan import Scan
from app.models.user import User
from app.models.whois import WhoisRecord
from app.services import geo


class _Resp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _seed(db, email, domain="shop.example", ips=("93.184.215.14",), country="MY"):
    user = db.query(User).filter(User.email == email).one()
    scan = Scan(domain=domain, status="completed", created_by=user.id,
                organization_id=user.organization_id, completed_at=datetime.now(timezone.utc))
    db.add(scan)
    db.flush()
    sub = Subdomain(scan_id=scan.id, hostname=domain, ip_addresses=list(ips), is_alive=True)
    db.add(sub)
    db.flush()
    db.add(DNSRecord(subdomain_id=sub.id, record_type="A", value="10.0.0.5"))
    db.add(WhoisRecord(domain=domain, scan_id=scan.id, registrant_country=country))
    db.commit()
    return scan


def setup_function():
    geo.clear_cache()


def test_parse_splits_asn_and_provider():
    out = geo._parse("1.1.1.1", {"country": "au", "city": "Sydney", "region": "NSW",
                                 "org": "AS13335 Cloudflare, Inc.", "anycast": True})
    assert out["country"] == "AU"
    assert out["asn"] == "AS13335"
    assert out["provider"] == "Cloudflare, Inc."
    assert out["anycast"] is True


def test_private_addresses_are_never_sent_out(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("private IP must not be looked up")

    monkeypatch.setattr(geo.requests, "get", boom)
    for ip in ("10.0.0.5", "192.168.1.1", "127.0.0.1", "203.0.113.10"):
        assert geo.lookup_ip(ip)["private"] is True


def test_lookup_errors_do_not_raise(monkeypatch):
    def down(*a, **k):
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(geo.requests, "get", down)
    assert geo.lookup_ip("8.8.8.8")["error"] == "unreachable"
    monkeypatch.setattr(geo.requests, "get", lambda *a, **k: _Resp(429))
    assert geo.lookup_ip("8.8.4.4")["error"] == "rate_limited"


def test_lookups_are_cached(monkeypatch):
    calls = []

    def fake(url, **kw):
        calls.append(url)
        return _Resp(200, {"country": "US", "city": "Ashburn", "org": "AS15133 Edgecast"})

    monkeypatch.setattr(geo.requests, "get", fake)
    geo.lookup_ip("93.184.215.14")
    geo.lookup_ip("93.184.215.14")
    assert len(calls) == 1


def test_unique_ips_skips_junk_and_duplicates():
    assert geo.unique_ips(["1.1.1.1", "1.1.1.1", "not-an-ip", None, " 8.8.8.8 "]) == ["1.1.1.1", "8.8.8.8"]


def test_endpoint_returns_registrant_and_hosting(client, auth_headers, db_session, monkeypatch):
    _seed(db_session, auth_headers["email"])
    monkeypatch.setattr(geo.requests, "get",
                        lambda url, **kw: _Resp(200, {"country": "US", "city": "Los Angeles",
                                                      "region": "California", "org": "AS15133 Edgecast"}))
    r = client.get("/api/v1/assets/whois/location", params={"domain": "Shop.Example."},
                   headers={"Authorization": auth_headers["Authorization"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["registrant_country"] == "MY"
    by_ip = {loc["ip"]: loc for loc in body["locations"]}
    assert by_ip["93.184.215.14"]["city"] == "Los Angeles"
    assert by_ip["93.184.215.14"]["provider"] == "Edgecast"
    assert by_ip["10.0.0.5"]["private"] is True


def test_endpoint_refuses_domains_outside_your_scans(client, auth_headers, db_session):
    _seed(db_session, auth_headers["email"])
    r = client.get("/api/v1/assets/whois/location", params={"domain": "other.example"},
                   headers={"Authorization": auth_headers["Authorization"]})
    assert r.status_code == 404
