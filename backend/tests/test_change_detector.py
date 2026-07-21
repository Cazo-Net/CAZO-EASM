"""Unit tests for change detection diff logic (pure function)."""
from app.services.change_detector import diff_scan_pair


def _snap(subs):
    return {
        "subdomains": {h: d for h, d in subs.items()},
        "ports": {h: [] for h in subs},
        "certs": {h: [] for h in subs},
        "techs": {h: [] for h in subs},
    }


class TestDiffScanPair:
    def test_added_subdomain(self):
        a = _snap({"a.example.com": {"is_alive": True, "ips": []}})
        b = _snap({
            "a.example.com": {"is_alive": True, "ips": []},
            "b.example.com": {"is_alive": True, "ips": []},
        })
        changes = diff_scan_pair(a, b)
        added = [c for c in changes if c["change_type"] == "added" and c["entity_type"] == "subdomain"]
        assert len(added) == 1
        assert added[0]["entity_key"] == "b.example.com"

    def test_removed_subdomain(self):
        a = _snap({"a.example.com": {}, "b.example.com": {}})
        b = _snap({"a.example.com": {}})
        changes = diff_scan_pair(a, b)
        removed = [c for c in changes if c["change_type"] == "removed" and c["entity_type"] == "subdomain"]
        assert len(removed) == 1

    def test_port_changes(self):
        a = _snap({"a.example.com": {}})
        a["ports"]["a.example.com"] = [{"port": 80, "service": "http", "state": "open"}]
        b = _snap({"a.example.com": {}})
        b["ports"]["a.example.com"] = [
            {"port": 80, "service": "http", "state": "open"},
            {"port": 443, "service": "https", "state": "open"},
        ]
        changes = diff_scan_pair(a, b)
        added_ports = [c for c in changes if c["change_type"] == "added" and c["entity_type"] == "port"]
        assert len(added_ports) == 1
        assert added_ports[0]["entity_key"] == "a.example.com:443"

    def test_no_changes(self):
        snap = _snap({"a.example.com": {}})
        assert diff_scan_pair(snap, snap) == []

    def test_empty_to_full(self):
        changes = diff_scan_pair(_snap({}), _snap({"x.example.com": {}}))
        assert len(changes) == 1
        assert changes[0]["change_type"] == "added"
