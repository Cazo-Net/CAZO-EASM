"""Unit tests for health/exposure scoring (pure functions)."""
from app.services.scoring import score_health, score_exposure


class TestHealthScoring:
    def test_full_health(self):
        r = score_health({"is_alive": True, "cert_valid": True, "cert_days_left": 90})
        assert r.score == 100.0

    def test_dead_asset(self):
        r = score_health({"is_alive": False})
        assert r.score < 100
        assert any("dead" in f["detail"].lower() for f in r.factors)

    def test_expired_cert(self):
        r = score_health({"is_alive": True, "cert_valid": True, "cert_days_left": -5})
        assert r.score <= 75

    def test_expiring_soon_cert(self):
        r = score_health({"is_alive": True, "cert_valid": True, "cert_days_left": 10})
        assert r.score < 100
        assert any("expires" in f["detail"].lower() for f in r.factors)

    def test_score_bounded(self):
        r = score_health({"is_alive": False, "cert_valid": False, "cert_days_left": -30, "tech_stale": True})
        assert 0.0 <= r.score <= 100.0


class TestExposureScoring:
    def test_no_exposure(self):
        r = score_exposure({"open_ports": [], "services": [], "severities": []})
        assert r.score == 0.0

    def test_open_ports_add(self):
        r = score_exposure({"open_ports": [80, 443, 22], "services": [], "severities": []})
        assert r.score > 0

    def test_sensitive_service(self):
        r = score_exposure({"open_ports": [3389], "services": ["rdp"], "severities": []})
        assert r.score >= 4

    def test_severity_load(self):
        r = score_exposure({"open_ports": [], "services": [], "severities": ["critical", "high"]})
        assert r.score >= 16

    def test_score_bounded(self):
        r = score_exposure({
            "open_ports": list(range(1000)),
            "services": ["rdp", "telnet", "ftp"],
            "severities": ["critical"] * 50,
        })
        assert 0.0 <= r.score <= 100.0
