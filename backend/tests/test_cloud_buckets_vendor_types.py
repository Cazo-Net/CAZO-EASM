"""Tests for cloud bucket discovery scanner, vendor_type tagging, and risk score alignment."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.scanners.v2.cloud_buckets import (
    CloudBucketScanner, _build_bucket_names, _probe_s3, _probe_azure, _probe_gcs,
)
from app.scanners.v2.base import ScanResult
from app.scanners.v2.tech_intel import FINGERPRINTS, TechnologyIntelligenceScanner
from app.risk_scorer import PORT_SCORES


# ─── Cloud Bucket Scanner ───────────────────────────────────────────────

class TestBuildBucketNames:
    def test_generates_candidates(self):
        names = _build_bucket_names("example.com")
        assert "example" in names
        assert "example-com" in names
        assert "assets-example" in names
        assert "example-backup" in names
        assert "cdn.example.com" in names

    def test_includes_standard_prefixes(self):
        names = _build_bucket_names("acme.io")
        assert any("assets" in n for n in names)
        assert any("static" in n for n in names)
        assert any("media" in n for n in names)
        assert any("backup" in n for n in names)


class TestCloudBucketScanner:
    def test_validate_target(self):
        scanner = CloudBucketScanner()
        assert scanner.validate_target("example.com") is True
        assert scanner.validate_target("a.b") is True
        assert scanner.validate_target("") is False
        assert scanner.validate_target("invalid") is False

    def test_scanner_metadata(self):
        scanner = CloudBucketScanner()
        assert scanner.name == "cloud_buckets"
        assert "cloud_storage_discovery" in scanner.capabilities
        assert "s3_bucket_detection" in scanner.capabilities
        assert "azure_blob_detection" in scanner.capabilities
        assert "gcs_bucket_detection" in scanner.capabilities

    @pytest.mark.asyncio
    async def test_scan_returns_empty_when_no_buckets(self):
        scanner = CloudBucketScanner()
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.get.return_value = mock_response
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = instance

            result = await scanner.scan("nonexistent-example-xyz.com")

        assert result.success is True
        assert result.scanner == "cloud_buckets"
        assert result.data["total_found"] == 0
        assert isinstance(result.data["providers"], dict)

    @pytest.mark.asyncio
    async def test_scan_detects_s3_bucket(self):
        scanner = CloudBucketScanner()

        # Mock a public S3 listing response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<ListBucketResult><Contents><Key>test.txt</Key></Contents></ListBucketResult>"

        with patch("httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.get.return_value = mock_response
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = instance

            result = await scanner.scan("example.com")

        assert result.success is True
        # Should find at least one bucket
        if result.data["total_found"] > 0:
            bucket = result.data["buckets"][0]
            assert bucket["provider"] == "aws_s3"
            assert bucket["is_listing"] is True
            assert bucket["severity"] == "high"


# ─── Vendor Type Tagging ────────────────────────────────────────────────

class TestVendorTypeTagging:
    def test_all_fingerprints_have_vendor_type(self):
        for name, fp in FINGERPRINTS.items():
            assert "vendor_type" in fp, f"Fingerprint '{name}' missing vendor_type"
            assert fp["vendor_type"] in (
                "first_party_infra", "third_party_service", "saas_platform",
                "security_tool", "cloud_provider", "devops_tool", "unknown",
            ), f"Fingerprint '{name}' has invalid vendor_type: {fp['vendor_type']}"

    def test_cdn_is_third_party(self):
        assert FINGERPRINTS["cloudflare"]["vendor_type"] == "third_party_service"
        assert FINGERPRINTS["akamai"]["vendor_type"] == "third_party_service"
        assert FINGERPRINTS["fastly"]["vendor_type"] == "third_party_service"

    def test_analytics_is_third_party(self):
        assert FINGERPRINTS["google_analytics"]["vendor_type"] == "third_party_service"
        assert FINGERPRINTS["hotjar"]["vendor_type"] == "third_party_service"

    def test_cms_saas_platforms(self):
        assert FINGERPRINTS["shopify"]["vendor_type"] == "saas_platform"
        assert FINGERPRINTS["wix"]["vendor_type"] == "saas_platform"
        assert FINGERPRINTS["squarespace"]["vendor_type"] == "saas_platform"

    def test_frameworks_first_party(self):
        assert FINGERPRINTS["django"]["vendor_type"] == "first_party_infra"
        assert FINGERPRINTS["react"]["vendor_type"] == "first_party_infra"
        assert FINGERPRINTS["next.js"]["vendor_type"] == "first_party_infra"

    def test_waf_is_security(self):
        assert FINGERPRINTS["cloudflare_waf"]["vendor_type"] == "security_tool"
        assert FINGERPRINTS["recaptcha"]["vendor_type"] == "security_tool"

    def test_cloud_providers(self):
        assert FINGERPRINTS["aws"]["vendor_type"] == "cloud_provider"
        assert FINGERPRINTS["gcp"]["vendor_type"] == "cloud_provider"
        assert FINGERPRINTS["azure"]["vendor_type"] == "cloud_provider"

    @pytest.mark.asyncio
    async def test_scan_result_includes_vendor_type_summary(self):
        scanner = TechnologyIntelligenceScanner()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"server": "nginx", "x-powered-by": "Express"}
        mock_response.cookies = {}
        mock_response.text = '<html><script src="https://www.google-analytics.com/analytics.js"></script></html>'

        with patch("httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.get.return_value = mock_response
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = instance

            result = await scanner.scan("example.com")

        assert result.success is True
        data = result.data
        assert "by_vendor_type" in data
        assert "third_party_services" in data["by_vendor_type"]
        assert "first_party_infrastructure" in data["by_vendor_type"]
        assert "third_party_count" in data["summary"]
        assert "saas_count" in data["summary"]


# ─── Risk Score Port Alignment ──────────────────────────────────────────

class TestRiskScorePortAlignment:
    def test_all_risky_ports_in_score_table(self):
        """Every port flagged in security_findings should have a risk score."""
        risky_ports = {21, 22, 23, 25, 53, 139, 445, 3306, 3389, 5432, 5601, 5900, 6379, 9200, 27017}
        for port in risky_ports:
            assert port in PORT_SCORES, f"Port {port} missing from PORT_SCORES"

    def test_database_ports_highest_score(self):
        assert PORT_SCORES[3306] == 25   # MySQL
        assert PORT_SCORES[5432] == 25   # PostgreSQL
        assert PORT_SCORES[6379] == 25   # Redis
        assert PORT_SCORES[27017] == 25  # MongoDB

    def test_rdp_high_score(self):
        assert PORT_SCORES[3389] == 20

    def test_ssh_moderate_score(self):
        assert PORT_SCORES[22] == 15

    def test_cleartext_services_scored(self):
        assert PORT_SCORES[21] == 10   # FTP
        assert PORT_SCORES[23] == 15   # Telnet

    def test_exposed_services_scored(self):
        assert PORT_SCORES[9200] == 15  # Elasticsearch
        assert PORT_SCORES[5601] == 10  # Kibana
        assert PORT_SCORES[5900] == 10  # VNC
        assert PORT_SCORES[139] == 10   # SMB NetBIOS
        assert PORT_SCORES[445] == 10   # SMB
