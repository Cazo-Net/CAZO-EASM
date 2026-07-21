"""Unit tests for the discovery plugin registry."""
from app.scanners.registry import registry, ScannerCategory, register_scanner, ScannerPlugin
from app.scanners.base import BaseScanner


class _DummyScanner(BaseScanner):
    async def scan(self, target, **kwargs):
        return {}

    def validate_target(self, target):
        return True


def test_builtin_plugins_registered():
    names = {p.name for p in registry.all()}
    # nuclei was intentionally removed and replaced by security-findings + cve-correlation
    for expected in ("subdomain", "dns", "whois", "ssl", "ports", "technology", "security-findings", "cve-correlation"):
        assert expected in names


def test_by_category():
    subdomain_plugins = registry.by_category(ScannerCategory.SUBDOMAIN)
    assert any(p.name in ("subdomain", "subfinder") for p in subdomain_plugins)


def test_set_enabled_toggles():
    # Register a temporary plugin and toggle it.
    @register_scanner(name="__test_plugin", category=ScannerCategory.DNS)
    class _T(_DummyScanner):
        pass

    plugin = registry.get("__test_plugin")
    assert plugin.enabled is True
    registry.set_enabled("__test_plugin", False)
    assert plugin.enabled is False
    # Restore for cleanliness.
    registry.set_enabled("__test_plugin", True)


def test_instantiate_returns_scanner():
    plugin = registry.by_category(ScannerCategory.DNS)[0]
    instance = plugin.instantiate()
    assert isinstance(instance, BaseScanner)


def test_discovery_manifest_shape():
    manifest = __import__("app.scanners", fromlist=["discovery_manifest"]).discovery_manifest()
    assert isinstance(manifest, list)
    assert all({"name", "category", "enabled"} <= set(m.keys()) for m in manifest)
