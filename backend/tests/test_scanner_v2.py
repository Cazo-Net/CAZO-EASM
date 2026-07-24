"""Integration tests for the v2 scanner framework.

Tests cover:
- Component imports and instantiation
- Registry plugin registration
- Pipeline stage ordering
- Risk engine scoring
- Graph engine construction
- V2ScanRunner adapter compatibility
- API route smoke tests
"""
from __future__ import annotations



# ── Component import tests ──

class TestV2Imports:
    def test_base_imports(self):
        from app.scanners.v2.base import EnhancedBaseScanner, ScanResult, ScannerMetrics, CircuitBreaker
        assert EnhancedBaseScanner is not None
        assert ScanResult is not None
        assert ScannerMetrics is not None
        assert CircuitBreaker is not None

    def test_registry_imports(self):
        from app.scanners.v2.registry import ScannerCategory, registry, register_scanner, ScannerPlugin
        assert ScannerCategory is not None
        assert registry is not None
        assert callable(register_scanner)
        assert ScannerPlugin is not None

    def test_pipeline_imports(self):
        from app.scanners.v2.pipeline import ScanPipeline, PipelineStage, PipelineResult, PipelineContext
        assert ScanPipeline is not None
        assert PipelineStage is not None
        assert PipelineResult is not None
        assert PipelineContext is not None

    def test_scanner_imports(self):
        from app.scanners.v2.asset_discovery import AdvancedAssetDiscoveryScanner
        from app.scanners.v2.subdomain_intel import SubdomainIntelligenceScanner
        from app.scanners.v2.network_intel import NetworkIntelligenceScanner
        from app.scanners.v2.tech_intel import TechnologyIntelligenceScanner
        from app.scanners.v2.cert_intel import CertificateIntelligenceScanner
        assert AdvancedAssetDiscoveryScanner is not None
        assert SubdomainIntelligenceScanner is not None
        assert NetworkIntelligenceScanner is not None
        assert TechnologyIntelligenceScanner is not None
        assert CertificateIntelligenceScanner is not None

    def test_analysis_imports(self):
        from app.scanners.v2.risk_engine import RiskScoringEngine, risk_engine
        from app.scanners.v2.graph_intel import AttackSurfaceGraph, build_graph_from_scan
        from app.scanners.v2.monitoring import ContinuousMonitor, monitor
        from app.scanners.v2.ai_analyst import SecurityAnalyst
        assert RiskScoringEngine is not None
        assert risk_engine is not None
        assert AttackSurfaceGraph is not None
        assert callable(build_graph_from_scan)
        assert ContinuousMonitor is not None
        assert monitor is not None
        assert SecurityAnalyst is not None

    def test_runner_imports(self):
        from app.scanners.v2.runner import EnhancedScanRunner, enhanced_runner
        from app.scanners.v2_runner import V2ScanRunner
        assert EnhancedScanRunner is not None
        assert enhanced_runner is not None
        assert V2ScanRunner is not None


# ── Registry tests ──

class TestScannerRegistry:
    def test_registry_has_scanners(self):
        from app.scanners.v2.registry import registry
        plugins = registry.all()
        assert len(plugins) >= 5

    def test_registry_categories(self):
        from app.scanners.v2.registry import registry, ScannerCategory
        plugins = registry.all()
        categories = {p.category for p in plugins}
        assert ScannerCategory.ASSET_DISCOVERY in categories
        assert ScannerCategory.NETWORK_INTELLIGENCE in categories
        assert ScannerCategory.TECHNOLOGY_FINGERPRINT in categories
        assert ScannerCategory.CERTIFICATE_ANALYSIS in categories

    def test_registry_by_category(self):
        from app.scanners.v2.registry import registry, ScannerCategory
        asset_plugins = registry.by_category(ScannerCategory.ASSET_DISCOVERY)
        assert len(asset_plugins) >= 1
        for p in asset_plugins:
            assert p.category == ScannerCategory.ASSET_DISCOVERY

    def test_registry_get_by_name(self):
        from app.scanners.v2.registry import registry
        plugin = registry.get("advanced-asset-discovery")
        assert plugin is not None
        assert plugin.name == "advanced-asset-discovery"

    def test_registry_instantiate(self):
        from app.scanners.v2.registry import registry
        plugin = registry.get("advanced-asset-discovery")
        scanner = plugin.instantiate()
        assert scanner is not None
        assert scanner.name == "advanced-asset-discovery"


# ── Pipeline tests ──

class TestPipeline:
    def test_pipeline_stages_ordered(self):
        from app.scanners.v2.pipeline import PipelineStage
        stages = list(PipelineStage)
        stage_names = [s.value for s in stages]
        assert stage_names.index("asset_discovery") < stage_names.index("network_intelligence")
        assert stage_names.index("network_intelligence") < stage_names.index("technology_fingerprint")
        assert stage_names.index("technology_fingerprint") < stage_names.index("certificate_analysis")
        assert stage_names.index("certificate_analysis") < stage_names.index("risk_evaluation")
        assert stage_names.index("risk_evaluation") < stage_names.index("graph_mapping")

    def test_pipeline_can_be_instantiated(self):
        from app.scanners.v2.pipeline import ScanPipeline
        pipeline = ScanPipeline()
        assert pipeline is not None


# ── Risk engine tests ──

class TestRiskEngine:
    def test_risk_engine_empty_data(self):
        from app.scanners.v2.risk_engine import risk_engine
        result = risk_engine.calculate({})
        assert "risk_score" in result
        assert "severity" in result
        assert isinstance(result["risk_score"], (int, float))

    def test_risk_engine_with_assets(self):
        from app.scanners.v2.risk_engine import risk_engine
        scan_data = {
            "subdomains": {"example.com": {}, "api.example.com": {}, "dev.example.com": {}},
            "ports": {"example.com": [80, 443], "api.example.com": [80, 443, 8080]},
            "technologies": {"example.com": [{"name": "nginx", "version": "1.18.0"}]},
            "certificates": {"example.com": {"grade": "A"}},
        }
        result = risk_engine.calculate(scan_data)
        assert result["risk_score"] >= 0
        assert result["severity"] in ["Low", "Medium", "High", "Critical"]

    def test_risk_engine_recommendations(self):
        from app.scanners.v2.risk_engine import risk_engine
        scan_data = {
            "subdomains": {"a.com": {}, "b.com": {}, "c.com": {}, "d.com": {}, "e.com": {}},
            "ports": {"a.com": [80, 443, 22, 21, 25, 3306]},
            "technologies": {"a.com": [{"name": "Apache Tomcat/7.0"}]},
        }
        result = risk_engine.calculate(scan_data)
        assert "recommendations" in result
        assert isinstance(result["recommendations"], list)


# ── Graph engine tests ──

class TestGraphEngine:
    def test_graph_builds_from_scan(self):
        from app.scanners.v2.graph_intel import build_graph_from_scan
        scan_data = {
            "subdomains": {"example.com": {}, "api.example.com": {}},
            "ports": {"example.com": [80, 443]},
            "technologies": {"example.com": [{"name": "nginx"}]},
        }
        graph = build_graph_from_scan(scan_data, "example.com")
        assert graph is not None
        assert len(graph.nodes) > 0

    def test_graph_attack_surface_map(self):
        from app.scanners.v2.graph_intel import build_graph_from_scan
        scan_data = {
            "subdomains": {"example.com": {}, "api.example.com": {}},
            "ports": {"example.com": [80, 443], "api.example.com": [80, 443, 8080]},
        }
        graph = build_graph_from_scan(scan_data, "example.com")
        surface = graph.get_attack_surface_map()
        assert "assets" in surface
        assert "relationships" in surface
        assert "high_risk_nodes" in surface


# ── Adapter tests ──

class TestV2Adapter:
    def test_v2_runner_can_be_instantiated(self):
        from app.scanners.v2_runner import V2ScanRunner
        runner = V2ScanRunner()
        assert runner is not None

    def test_enhanced_runner_can_be_instantiated(self):
        from app.scanners.v2.runner import EnhancedScanRunner
        runner = EnhancedScanRunner()
        assert runner is not None


# ── API route smoke tests ──

class TestV2APIRoutes:
    def test_health_endpoint(self, client):
        resp = client.get("/api/v1/scanner-v2/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["engine"] == "v2"
        assert len(data["registered_scanners"]) >= 5
        assert len(data["pipeline_stages"]) >= 6

    def test_plugins_endpoint(self, client):
        resp = client.get("/api/v1/scanner-v2/plugins")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 5
        assert len(data["plugins"]) >= 5

    def test_scan_endpoint_requires_auth(self, client):
        resp = client.post("/api/v1/scanner-v2/scan", json={
            "domain": "example.com",
            "scan_type": "quick",
        })
        assert resp.status_code in (401, 403, 422)

    def test_monitor_crud(self, client, auth_headers, db_session):
        # Upgrade user to admin role so they have CREATE_SCAN permission
        from app.models.user import User
        user = db_session.query(User).filter(User.email == auth_headers["email"]).first()
        if user:
            user.role = "admin"
            db_session.commit()

        # Create
        resp = client.post("/api/v1/scanner-v2/monitor", json={
            "domain": "example.com",
            "interval_hours": 12,
        }, headers=auth_headers)
        assert resp.status_code == 200
        monitor_id = resp.json()["id"]

        # List
        resp = client.get("/api/v1/scanner-v2/monitor", headers=auth_headers)
        assert resp.status_code == 200
        monitors = resp.json()
        assert any(m["id"] == monitor_id for m in monitors)

        # Delete
        resp = client.delete(f"/api/v1/scanner-v2/monitor/{monitor_id}", headers=auth_headers)
        assert resp.status_code == 204
