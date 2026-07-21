"""Discovery plugin registry.

Implements the plugin architecture for discovery modules. Each scanner subclasses
:class:`~app.scanners.base.BaseScanner` and registers itself via the
``@register_scanner`` decorator (or by being imported). The
:class:`ScannerRegistry` then exposes the active plugin set, so the
:class:`~app.scanners.runner.ScanRunner` orchestrates discovery without
hardcoding scanner classes.

Adding a new discovery source is now a matter of:
1. Implementing a ``BaseScanner`` subclass.
2. Decorating it with ``@register_scanner`` and declaring its metadata.
No edits to ``runner.py`` or ``scan_service.py`` are required.
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Type

from app.scanners.base import BaseScanner

logger = logging.getLogger(__name__)


class ScannerCategory(str, Enum):
    SUBDOMAIN = "subdomain"
    DNS = "dns"
    WHOIS = "whois"
    SSL = "ssl"
    PORT = "port"
    TECHNOLOGY = "technology"
    VULNERABILITY = "vulnerability"


@dataclass
class ScannerPlugin:
    """Metadata + factory for a registered discovery module."""
    name: str
    category: ScannerCategory
    scanner_cls: Type[BaseScanner]
    enabled: bool = True
    description: str = ""
    # Optional scope gate: if True the runner checks each target against the
    # org's authorized scopes before invoking (default True for safety).
    requires_scope: bool = True
    # Singleton instance cache (scanners are stateless apart from config).
    _instance: Optional[BaseScanner] = field(default=None, repr=False)

    def instantiate(self, config: Optional[dict] = None) -> BaseScanner:
        if self._instance is None:
            self._instance = self.scanner_cls(config or {})
        return self._instance


class ScannerRegistry:
    """Central registry of discovery plugins."""

    def __init__(self) -> None:
        self._plugins: Dict[str, ScannerPlugin] = {}

    def register(self, plugin: ScannerPlugin) -> ScannerPlugin:
        if plugin.name in self._plugins:
            logger.warning("Scanner '%s' already registered; overwriting.", plugin.name)
        self._plugins[plugin.name] = plugin
        logger.debug("Registered scanner plugin '%s' (%s)", plugin.name, plugin.category)
        return plugin

    def get(self, name: str) -> Optional[ScannerPlugin]:
        return self._plugins.get(name)

    def all(self) -> List[ScannerPlugin]:
        return list(self._plugins.values())

    def enabled(self) -> List[ScannerPlugin]:
        return [p for p in self._plugins.values() if p.enabled]

    def by_category(self, category: ScannerCategory) -> List[ScannerPlugin]:
        return [p for p in self.enabled() if p.category == category]

    def set_enabled(self, name: str, enabled: bool) -> None:
        plugin = self._plugins.get(name)
        if plugin:
            plugin.enabled = enabled


# Process-wide registry singleton.
registry = ScannerRegistry()


def register_scanner(
    name: str,
    category: ScannerCategory,
    enabled: bool = True,
    description: str = "",
    requires_scope: bool = True,
):
    """Class decorator that registers a scanner subclass as a plugin."""

    def decorator(cls: Type[BaseScanner]) -> Type[BaseScanner]:
        registry.register(
            ScannerPlugin(
                name=name,
                category=category,
                scanner_cls=cls,
                enabled=enabled,
                description=description,
                requires_scope=requires_scope,
            )
        )
        return cls

    return decorator


def discovery_manifest() -> List[dict]:
    """Machine-readable list of available discovery plugins (for API/docs)."""
    return [
        {
            "name": p.name,
            "category": p.category.value,
            "enabled": p.enabled,
            "description": p.description,
            "requires_scope": p.requires_scope,
        }
        for p in registry.all()
    ]
