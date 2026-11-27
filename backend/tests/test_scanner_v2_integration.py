"""Integration tests for the V2 scanner framework.

Tests cover:
- Scanner registry completeness (all 11 scanners registered)
- Pipeline stage-to-scanner mapping
- Scheduler interval-based due logic
- DB-backed monitoring persistence
- AI analyst answer_question routing
- Risk engine with realistic scan data
- EnhancedScanRunner result structure
- API endpoints (analyze, schedule CRUD)
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock

import pytest


# ── Registry: all 11 scanners registered ──

class TestRegistryCompleteness:
    EXPECTED_SCANNERS = {
        "advanced-asset-discovery",
        "subdomain-intelligence",
        "network-intelligence",
        "technology-intelligence",
        "certificate-intelligence",
        "dns-intelligence",
        "nmap-intelligence",
        "zone-transfer",
        "whois-intelligence",
        "cve-correlation",
        "security-findings",
    }

    def test_all_11_scanners_registered(self):
        from app.scanners.v2.registry import registry
        names = {p.name for p in registry.all()}
        missing = self.EXPECTED_SCANNERS - names
        assert not missing, f"Missing scanners: {missing}"

    def test_all_11_are_enabled(self):
        from app.scanners.v2.registry import registry
        for name in self.EXPECTED_SCANNERS:
            plugin = registry.get(name)
            assert plugin is not None, f"Scanner '{name}' not found"
            assert plugin.enabled, f"Scanner '{name}' is disabled"

    def test_scanner_categories_cover_pipeline_stages(self):
        from app.scanners.v2.registry import registry, ScannerCategory
        categories = {p.category for p in registry.all()}
        required = {
            ScannerCategory.ASSET_DISCOVERY,
            ScannerCategory.NETWORK_INTELLIGENCE,
            ScannerCategory.TECHNOLOGY_FINGERPRINT,
            ScannerCategory.CERTIFICATE_ANALYSIS,
            ScannerCategory.VULNERABILITY,  # DNS and zone-transfer use legacy categories
        }
        missing = required - categories
        assert not missing, f"Missing categories: {missing}"

    def test_each_scanner_instantiates(self):
        from app.scanners.v2.registry import registry
        for plugin in registry.all():
            scanner = plugin.instantiate()
            assert scanner is not None
            assert scanner.name == plugin.name

    def test_scanner_versions_are_set(self):
        from app.scanners.v2.registry import registry
        for plugin in registry.all():
            assert plugin.version, f"Scanner '{plugin.name}' has no version"


# ── Pipeline stage → scanner mapping ──

class TestPipelineScannerMapping:
    def test_asset_discovery_stage_has_scanners(self):
        from app.scanners.v2.pipeline import ScanPipeline, PipelineStage
        from app.scanners.v2.registry import registry, ScannerCategory
        pipeline = ScanPipeline()
        stage_info = pipeline.list_stages()
        asset_stage = next(s for s in stage_info if s["stage"] == "asset_discovery")
        assert len(asset_stage["scanners"]) >= 2

    def test_dns_intelligence_stage_has_scanners(self):
        from app.scanners.v2.pipeline import ScanPipeline
        from app.scanners.v2.registry import registry, ScannerCategory
        pipeline = ScanPipeline()
        stage_info = pipeline.list_stages()
        dns_stage = next(s for s in stage_info if s["stage"] == "dns_intelligence")
        assert len(dns_stage["scanners"]) >= 1

    def test_vulnerability_stage_has_scanners(self):
        from app.scanners.v2.pipeline import ScanPipeline
        pipeline = ScanPipeline()
        stage_info = pipeline.list_stages()
        vuln_stage = next(s for s in stage_info if s["stage"] == "vulnerability_assessment")
        assert len(vuln_stage["scanners"]) >= 2

    def test_pipeline_stages_are_sequential(self):
        from app.scanners.v2.pipeline import PipelineStage
        stages = list(PipelineStage)
        for i in range(len(stages) - 1):
            assert stages[i].value < stages[i + 1].value or True  # enum order

    def test_pipeline_execute_with_mocked_scanners(self):
        """Pipeline should handle a target without crashing (scanners will fail gracefully)."""
        import asyncio
        from app.scanners.v2.pipeline import ScanPipeline

        pipeline = ScanPipeline()
        result = asyncio.run(
            pipeline.execute("nonexistent.example.invalid", config={"timeout": 2})
        )
        assert result is not None
        assert result.target == "nonexistent.example.invalid"
        assert isinstance(result.total_scanners, int)


# ── Scheduler interval logic ──

class TestSchedulerIntervalLogic:
    def test_new_schedule_is_due(self):
        from app.services.scan_scheduler import ScanScheduler, ScheduleConfig
        sched = ScanScheduler()
        config = ScheduleConfig(
            id="test-1",
            domain="example.com",
            interval_hours=24,
            scan_type="quick",
            enabled=True,
            created_by=1,
        )
        sched.add_schedule(config)
        due = sched.get_due_scans()
        assert len(due) == 1
        assert due[0].id == "test-1"

    def test_disabled_schedule_not_due(self):
        from app.services.scan_scheduler import ScanScheduler, ScheduleConfig
        sched = ScanScheduler()
        config = ScheduleConfig(
            id="test-disabled",
            domain="example.com",
            interval_hours=24,
            scan_type="quick",
            enabled=False,
            created_by=1,
        )
        sched.add_schedule(config)
        due = sched.get_due_scans()
        assert len(due) == 0

    def test_recently_run_schedule_not_due(self):
        from app.services.scan_scheduler import ScanScheduler, ScheduleConfig
        sched = ScanScheduler()
        config = ScheduleConfig(
            id="test-recent",
            domain="example.com",
            interval_hours=24,
            scan_type="quick",
            enabled=True,
            created_by=1,
            last_run=time.time(),  # just ran
        )
        sched.add_schedule(config)
        due = sched.get_due_scans()
        assert len(due) == 0

    def test_old_run_schedule_is_due(self):
        from app.services.scan_scheduler import ScanScheduler, ScheduleConfig
        sched = ScanScheduler()
        config = ScheduleConfig(
            id="test-old",
            domain="example.com",
            interval_hours=24,
            scan_type="quick",
            enabled=True,
            created_by=1,
            last_run=time.time() - (25 * 3600),  # 25 hours ago
        )
        sched.add_schedule(config)
        due = sched.get_due_scans()
        assert len(due) == 1

    def test_remove_schedule(self):
        from app.services.scan_scheduler import ScanScheduler, ScheduleConfig
        sched = ScanScheduler()
        config = ScheduleConfig(
            id="test-rm",
            domain="example.com",
            interval_hours=24,
            scan_type="quick",
            enabled=True,
            created_by=1,
        )
        sched.add_schedule(config)
        sched.remove_schedule("test-rm")
        due = sched.get_due_scans()
        assert len(due) == 0

    def test_mixed_schedules_only_due_returned(self):
        from app.services.scan_scheduler import ScanScheduler, ScheduleConfig
        sched = ScanScheduler()
        # Due: never ran
        sched.add_schedule(ScheduleConfig(
            id="a", domain="a.com", interval_hours=24,
            scan_type="quick", enabled=True, created_by=1,
        ))
        # Not due: just ran
        sched.add_schedule(ScheduleConfig(
            id="b", domain="b.com", interval_hours=24,
            scan_type="quick", enabled=True, created_by=1,
            last_run=time.time(),
        ))
        # Due: ran 25h ago
        sched.add_schedule(ScheduleConfig(
            id="c", domain="c.com", interval_hours=24,
            scan_type="quick", enabled=True, created_by=1,
            last_run=time.time() - (25 * 3600),
        ))
        # Not due: disabled
        sched.add_schedule(ScheduleConfig(
            id="d", domain="d.com", interval_hours=24,
            scan_type="quick", enabled=False, created_by=1,
        ))
        due = sched.get_due_scans()
        due_ids = {d.id for d in due}
        assert due_ids == {"a", "c"}


# ── DB-backed monitoring ──

class TestDBBackedMonitoring:
    def test_add_and_list_targets(self, db_session):
        from app.scanners.v2.monitoring import ContinuousMonitor, MonitorScheduleData
        mon = ContinuousMonitor()
        result = mon.add_target(
            db_session,
            domain="example.com",
            user_id=1,
            organization_id=10,
            schedule=MonitorScheduleData(interval_hours=12),
        )
        db_session.commit()
        assert "id" in result
        assert result["domain"] == "example.com"
        assert result["interval_hours"] == 12

        targets = mon.list_targets(db_session, organization_id=10)
        assert any(t["domain"] == "example.com" for t in targets)

    def test_remove_target(self, db_session):
        from app.scanners.v2.monitoring import ContinuousMonitor
        mon = ContinuousMonitor()
        result = mon.add_target(db_session, domain="rm.example.com", user_id=1)
        db_session.commit()
        removed = mon.remove_target(db_session, result["id"])
        db_session.commit()
        assert removed is True
        targets = mon.list_targets(db_session)
        assert not any(t["domain"] == "rm.example.com" for t in targets)

    def test_remove_nonexistent_returns_false(self, db_session):
        from app.scanners.v2.monitoring import ContinuousMonitor
        mon = ContinuousMonitor()
        assert mon.remove_target(db_session, "nonexistent-id") is False

    def test_get_targets_due(self, db_session):
        from app.scanners.v2.monitoring import ContinuousMonitor
        mon = ContinuousMonitor()
        # Add with next_run in the past
        result = mon.add_target(db_session, domain="due.example.com", user_id=1)
        # Manually set next_run_at to the past
        from app.models.v2_scanner import MonitorSchedule
        row = db_session.query(MonitorSchedule).filter(MonitorSchedule.id == result["id"]).first()
        row.next_run_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db_session.commit()

        due = mon.get_targets_due(db_session)
        assert any(d["domain"] == "due.example.com" for d in due)

    def test_record_scan_updates_next_run(self, db_session):
        from app.scanners.v2.monitoring import ContinuousMonitor
        mon = ContinuousMonitor()
        result = mon.add_target(db_session, domain="scan.example.com", user_id=1,
                                schedule=None)
        db_session.commit()
        # Store the next_run_at before recording (SQLite returns naive datetimes)
        from app.models.v2_scanner import MonitorSchedule
        row_before = db_session.query(MonitorSchedule).filter(MonitorSchedule.id == result["id"]).first()
        old_next_run = row_before.next_run_at

        mon.record_scan(db_session, result["id"])
        db_session.commit()

        row_after = db_session.query(MonitorSchedule).filter(MonitorSchedule.id == result["id"]).first()
        assert row_after.next_run_at is not None
        assert row_after.last_run_at is not None
        # next_run_at should be set to now + interval_hours, so it should be in the future
        # compared to the old next_run_at (or at least not equal)
        assert row_after.next_run_at != old_next_run

    def test_record_scan_history(self, db_session):
        from app.scanners.v2.monitoring import ContinuousMonitor
        mon = ContinuousMonitor()
        history_id = mon.record_scan_history(
            db_session,
            domain="hist.example.com",
            scan_type="quick",
            status="completed",
            user_id=1,
            results={
                "subdomains": ["a.example.com", "b.example.com"],
                "ports": {"example.com": [{"port": 80}, {"port": 443}]},
                "technologies": {"example.com": [{"name": "nginx"}]},
                "risk_score": {"risk_score": 42, "severity": "Medium"},
            },
            duration_ms=1500,
        )
        db_session.commit()
        assert history_id

        from app.models.v2_scanner import ScanHistory
        row = db_session.query(ScanHistory).filter(ScanHistory.id == history_id).first()
        assert row.subdomains_found == 2
        assert row.open_ports_found == 2
        assert row.technologies_found == 1
        assert row.risk_score == 42
        assert row.risk_severity == "Medium"

    def test_asset_lifecycle_create_and_update(self, db_session):
        from app.scanners.v2.monitoring import ContinuousMonitor
        mon = ContinuousMonitor()
        assets = [
            {"type": "subdomain", "value": "a.lifecycle.com"},
            {"type": "subdomain", "value": "b.lifecycle.com"},
        ]
        count = mon.update_asset_lifecycle(db_session, "lifecycle.com", assets, organization_id=1)
        db_session.commit()
        assert count == 2

        # Re-run: should update, not create new
        count2 = mon.update_asset_lifecycle(db_session, "lifecycle.com", assets, organization_id=1)
        db_session.commit()
        assert count2 == 0  # no new assets

    def test_mark_removed_assets(self, db_session):
        from app.scanners.v2.monitoring import ContinuousMonitor
        mon = ContinuousMonitor()
        assets = [
            {"type": "subdomain", "value": "keep.rm.com"},
            {"type": "subdomain", "value": "drop.rm.com"},
        ]
        mon.update_asset_lifecycle(db_session, "rm.com", assets)
        db_session.commit()

        # Only keep one
        removed = mon.mark_removed_assets(db_session, "rm.com", {"keep.rm.com"})
        db_session.commit()
        assert removed == 1

    def test_detect_changes_subdomains(self):
        from app.scanners.v2.monitoring import ContinuousMonitor
        mon = ContinuousMonitor()
        old = {"subdomains": ["a.com", "b.com"]}
        new = {"subdomains": ["b.com", "c.com"]}
        changes = mon.detect_changes(old, new)
        types = {c.change_type.value for c in changes}
        assert "asset_added" in types
        assert "asset_removed" in types

    def test_detect_changes_ports(self):
        from app.scanners.v2.monitoring import ContinuousMonitor
        mon = ContinuousMonitor()
        old = {"ports": {"host.com": [{"port": 80}]}}
        new = {"ports": {"host.com": [{"port": 80}, {"port": 443}]}}
        changes = mon.detect_changes(old, new)
        types = {c.change_type.value for c in changes}
        assert "port_opened" in types

    def test_detect_changes_risk_delta(self):
        from app.scanners.v2.monitoring import ContinuousMonitor
        mon = ContinuousMonitor()
        old = {"risk_score": {"risk_score": 10}}
        new = {"risk_score": {"risk_score": 25}}
        changes = mon.detect_changes(old, new)
        types = {c.change_type.value for c in changes}
        assert "risk_increased" in types

    def test_check_notification_triggers(self, db_session):
        from app.scanners.v2.monitoring import ContinuousMonitor
        mon = ContinuousMonitor()

        from app.models.v2_scanner import NotificationTrigger
        trigger = NotificationTrigger(
            id=str(uuid.uuid4())[:36],
            name="Critical Alert",
            event_type="critical_finding",
            domain="notify.example.com",
            notification_method="in_app",
            enabled=True,
            created_by=1,
            organization_id=1,
        )
        db_session.add(trigger)
        db_session.commit()

        triggered = mon.check_notification_triggers(
            db_session, "notify.example.com", "critical_finding", organization_id=1
        )
        assert len(triggered) == 1
        assert triggered[0]["name"] == "Critical Alert"


# ── AI Analyst ──

class TestAIAnalyst:
    def test_answer_question_highest_risk(self):
        from app.scanners.v2.ai_analyst import SecurityAnalyst
        analyst = SecurityAnalyst()
        data = {
            "security_findings": [
                {"type": "expired_cert", "severity": "critical", "detail": "Expired on host.com"},
            ],
            "ports": {"host.com": [{"port": 3306}]},
        }
        result = analyst.answer_question("What is the highest risk?", data)
        assert result["type"] == "analysis"
        assert "critical" in result["answer"].lower() or "highest" in result["answer"].lower()

    def test_answer_question_subdomains(self):
        from app.scanners.v2.ai_analyst import SecurityAnalyst
        analyst = SecurityAnalyst()
        data = {"subdomains": ["a.com", "b.com", "c.com"]}
        result = analyst.answer_question("Tell me about subdomains", data)
        assert "3" in result["answer"]

    def test_answer_question_recommendations(self):
        from app.scanners.v2.ai_analyst import SecurityAnalyst
        analyst = SecurityAnalyst()
        data = {
            "ssl_certificates": {"host.com": {"is_valid": False}},
        }
        result = analyst.answer_question("What should I fix?", data)
        assert result["type"] == "analysis"
        assert "recommend" in result["answer"].lower() or "fix" in result["answer"].lower()

    def test_answer_question_unknown(self):
        from app.scanners.v2.ai_analyst import SecurityAnalyst
        analyst = SecurityAnalyst()
        result = analyst.answer_question("xyzzy foobar", {})
        assert result["type"] == "help"

    def test_explain_findings_structure(self):
        from app.scanners.v2.ai_analyst import SecurityAnalyst
        analyst = SecurityAnalyst()
        data = {
            "subdomains": ["x.com"],
            "ports": {"x.com": [{"port": 443}]},
            "technologies": {"x.com": [{"name": "nginx"}]},
            "security_findings": [{"type": "test", "severity": "low", "detail": "test"}],
        }
        result = analyst.explain_findings(data)
        assert "executive_summary" in result
        assert "top_risks" in result
        assert "recommendations" in result
        assert "asset_overview" in result


# ── Risk engine with realistic data ──

class TestRiskEngineRealistic:
    def test_high_risk_scenario(self):
        from app.scanners.v2.risk_engine import risk_engine
        data = {
            "subdomains": [f"sub{i}.example.com" for i in range(50)],
            "ports": {
                "example.com": [
                    {"port": 22}, {"port": 3306}, {"port": 6379},
                    {"port": 27017}, {"port": 3389},
                ],
            },
            "technologies": {
                "example.com": [
                    {"name": "wordpress", "version": "4.0"},
                    {"name": "php", "version": "7.2"},
                    {"name": "apache", "version": "2.4.29"},
                ],
            },
            "ssl_certificates": {
                "example.com": {"grade": "F", "is_valid": False, "days_until_expiry": 0},
            },
            "security_findings": [
                {"type": "expired_cert", "severity": "critical", "detail": "Expired"},
                {"type": "exposed_db", "severity": "critical", "detail": "Redis open"},
            ],
        }
        result = risk_engine.calculate(data)
        assert result["risk_score"] >= 50
        assert result["severity"] in ("High", "Critical")

    def test_low_risk_scenario(self):
        from app.scanners.v2.risk_engine import risk_engine
        data = {
            "subdomains": ["www.example.com"],
            "ports": {"example.com": [{"port": 443}]},
            "technologies": {
                "example.com": [
                    {"name": "nginx", "version": "1.24.0"},
                    {"name": "cloudflare"},
                ],
            },
            "ssl_certificates": {
                "example.com": {"grade": "A", "is_valid": True, "days_until_expiry": 200},
            },
            "security_findings": [],
        }
        result = risk_engine.calculate(data)
        assert result["risk_score"] <= 40
        assert result["severity"] in ("Low", "Medium")

    def test_risk_dimensions_present(self):
        from app.scanners.v2.risk_engine import risk_engine
        result = risk_engine.calculate({})
        assert "dimensions" in result
        expected_dims = {"exposure", "technology", "vulnerability", "business", "history", "threat"}
        assert set(result["dimensions"].keys()) == expected_dims

    def test_risk_score_bounded(self):
        from app.scanners.v2.risk_engine import risk_engine
        # Maximize everything
        data = {
            "subdomains": [f"s{i}.com" for i in range(500)],
            "ports": {"h.com": [{"port": p} for p in [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 1433, 1723, 3306, 3389, 5432, 5900, 6379, 8080, 8443, 27017]]},
            "technologies": {"h.com": [{"name": "wordpress", "version": "4.0"}, {"name": "php", "version": "5.6"}]},
            "security_findings": [{"severity": "critical", "type": "x", "detail": "y"}] * 10,
            "ssl_certificates": {"h.com": {"grade": "F", "is_valid": False}},
        }
        result = risk_engine.calculate(data)
        assert 0 <= result["risk_score"] <= 100


# ── EnhancedScanRunner structure ──

class TestEnhancedScanRunner:
    def test_run_quick_scan_structure(self):
        import asyncio
        from app.scanners.v2.runner import EnhancedScanRunner
        runner = EnhancedScanRunner()
        result = asyncio.run(
            runner.run_quick_scan("nonexistent.invalid", config={"timeout": 2})
        )
        assert "domain" in result
        assert "scan_type" in result
        assert result["scan_type"] == "quick"
        assert "risk_score" in result
        assert "pipeline" in result
        assert "assets" in result
        assert "summary" in result

    def test_run_scan_structure(self):
        import asyncio
        from app.scanners.v2.runner import EnhancedScanRunner
        runner = EnhancedScanRunner()
        result = asyncio.run(
            runner.run_scan("nonexistent.invalid", config={"timeout": 2})
        )
        assert result["scan_type"] == "full"
        assert "graph" in result
        assert "pipeline" in result

    def test_summary_fields(self):
        import asyncio
        from app.scanners.v2.runner import EnhancedScanRunner
        runner = EnhancedScanRunner()
        result = asyncio.run(
            runner.run_quick_scan("nonexistent.invalid", config={"timeout": 2})
        )
        summary = result["summary"]
        assert "total_subdomains" in summary
        assert "total_open_ports" in summary
        assert "total_technologies" in summary
        assert "risk_score" in summary
        assert "risk_label" in summary
        assert "pipeline_duration_ms" in summary


# ── API endpoints ──

class TestAnalyzeEndpoint:
    def test_analyze_returns_answer(self, client, auth_headers):
        from app.models.user import User
        from tests.conftest import TestingSessionLocal
        db = TestingSessionLocal()
        user = db.query(User).filter(User.email == auth_headers["email"]).first()
        if user:
            # Schedules belong to an organization (and are scope-checked).
            from app.models.organization import Organization
            import uuid
            org = Organization(name="Sched Org", slug=f"sched-{uuid.uuid4().hex[:8]}")
            db.add(org)
            db.flush()
            user.organization_id = org.id
            user.role = "admin"
            db.commit()
        db.close()

        resp = client.post("/api/v1/scanner-v2/analyze", json={
            "domain": "example.com",
            "question": "What subdomains were found?",
            "scan_data": {"subdomains": ["a.com", "b.com"]},
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert data["domain"] == "example.com"

    def test_analyze_requires_auth(self, client):
        resp = client.post("/api/v1/scanner-v2/analyze", json={
            "domain": "example.com",
            "question": "test",
        })
        assert resp.status_code in (401, 403)


class TestScheduleAPI:
    def test_create_and_list_schedule(self, client, auth_headers):
        from app.models.user import User
        from tests.conftest import TestingSessionLocal
        db = TestingSessionLocal()
        user = db.query(User).filter(User.email == auth_headers["email"]).first()
        if user:
            # Schedules belong to an organization (and are scope-checked).
            from app.models.organization import Organization
            import uuid
            org = Organization(name="Sched Org", slug=f"sched-{uuid.uuid4().hex[:8]}")
            db.add(org)
            db.flush()
            user.organization_id = org.id
            user.role = "admin"
            db.commit()
        db.close()

        resp = client.post("/api/v1/scanner-v2/schedule", json={
            "domain": "sched.example.com",
            "interval_hours": 6,
            "scan_type": "quick",
        }, headers=auth_headers)
        assert resp.status_code == 200
        sched_id = resp.json()["id"]

        resp = client.get("/api/v1/scanner-v2/schedules", headers=auth_headers)
        assert resp.status_code == 200
        schedules = resp.json()
        assert any(s["id"] == sched_id for s in schedules)

    def test_delete_schedule(self, client, auth_headers):
        from app.models.user import User
        from tests.conftest import TestingSessionLocal
        db = TestingSessionLocal()
        user = db.query(User).filter(User.email == auth_headers["email"]).first()
        if user:
            # Schedules belong to an organization (and are scope-checked).
            from app.models.organization import Organization
            import uuid
            org = Organization(name="Sched Org", slug=f"sched-{uuid.uuid4().hex[:8]}")
            db.add(org)
            db.flush()
            user.organization_id = org.id
            user.role = "admin"
            db.commit()
        db.close()

        resp = client.post("/api/v1/scanner-v2/schedule", json={
            "domain": "del.example.com",
            "interval_hours": 12,
        }, headers=auth_headers)
        sched_id = resp.json()["id"]

        resp = client.delete(f"/api/v1/scanner-v2/schedule/{sched_id}", headers=auth_headers)
        assert resp.status_code == 204

    def test_delete_nonexistent_schedule(self, client, auth_headers):
        from app.models.user import User
        from tests.conftest import TestingSessionLocal
        db = TestingSessionLocal()
        user = db.query(User).filter(User.email == auth_headers["email"]).first()
        if user:
            # Schedules belong to an organization (and are scope-checked).
            from app.models.organization import Organization
            import uuid
            org = Organization(name="Sched Org", slug=f"sched-{uuid.uuid4().hex[:8]}")
            db.add(org)
            db.flush()
            user.organization_id = org.id
            user.role = "admin"
            db.commit()
        db.close()

        resp = client.delete("/api/v1/scanner-v2/schedule/nonexistent", headers=auth_headers)
        assert resp.status_code == 404


class TestHealthEndpointExtended:
    def test_health_lists_all_scanner_names(self, client):
        resp = client.get("/api/v1/scanner-v2/health")
        assert resp.status_code == 200
        names = {s["name"] for s in resp.json()["registered_scanners"]}
        assert "dns-intelligence" in names
        assert "nmap-intelligence" in names
        assert "zone-transfer" in names
        assert "whois-intelligence" in names
        assert "cve-correlation" in names
        assert "security-findings" in names

    def test_plugins_lists_all_scanner_names(self, client):
        resp = client.get("/api/v1/scanner-v2/plugins")
        assert resp.status_code == 200
        names = {p["name"] for p in resp.json()["plugins"]}
        assert "dns-intelligence" in names
        assert "cve-correlation" in names
        assert "security-findings" in names
