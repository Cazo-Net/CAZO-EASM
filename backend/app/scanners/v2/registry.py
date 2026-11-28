"""Enhanced scanner registry with versioning, health checks, and dependency resolution.

Extends the v1 registry with:
- Semantic versioning per plugin
- Health-check endpoints per scanner
- Dependency graph resolution (topological sort)
- Runtime enable/disable with audit trail
- Category-based grouping for pipeline construction
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Type

from app.scanners.v2.base import EnhancedBaseScanner, ScannerPriority

logger = logging.getLogger(__name__)


class ScannerCategory(str, Enum):
    """Pipeline-ordered categories — execution flows top-to-bottom."""
    ASSET_DISCOVERY = "asset_discovery"
    DNS_INTELLIGENCE = "dns_intelligence"
    NETWORK_INTELLIGENCE = "network_intelligence"
    TECHNOLOGY_FINGERPRINT = "technology_fingerprint"
    CERTIFICATE_ANALYSIS = "certificate_analysis"
    WEB_EXPOSURE = "web_exposure"
    VULNERABILITY_ASSESSMENT = "vulnerability_assessment"
    RISK_EVALUATION = "risk_evaluation"
    GRAPH_MAPPING = "graph_mapping"
    # Legacy categories (kept for v1 compat)
    SUBDOMAIN = "subdomain"
    DNS = "dns"
    WHOIS = "whois"
    SSL = "ssl"
    PORT = "port"
    TECHNOLOGY = "technology"
    VULNERABILITY = "vulnerability"


# Pipeline execution order
CATEGORY_ORDER: Dict[ScannerCategory, int] = {
    ScannerCategory.ASSET_DISCOVERY: 10,
    ScannerCategory.DNS_INTELLIGENCE: 20,
    ScannerCategory.NETWORK_INTELLIGENCE: 30,
    ScannerCategory.TECHNOLOGY_FINGERPRINT: 40,
    ScannerCategory.CERTIFICATE_ANALYSIS: 50,
    ScannerCategory.WEB_EXPOSURE: 55,
    ScannerCategory.VULNERABILITY_ASSESSMENT: 60,
    ScannerCategory.RISK_EVALUATION: 70,
    ScannerCategory.GRAPH_MAPPING: 80,
    ScannerCategory.SUBDOMAIN: 10,
    ScannerCategory.DNS: 20,
    ScannerCategory.WHOIS: 20,
    ScannerCategory.SSL: 50,
    ScannerCategory.PORT: 30,
    ScannerCategory.TECHNOLOGY: 40,
    ScannerCategory.VULNERABILITY: 60,
}


@dataclass
class ScannerPlugin:
    """Metadata + factory for a registered scanner."""
    name: str
    category: ScannerCategory
    scanner_cls: Type[EnhancedBaseScanner]
    enabled: bool = True
    description: str = ""
    version: str = "1.0.0"
    priority: ScannerPriority = ScannerPriority.NORMAL
    requires_scope: bool = True
    dependencies: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    # Runtime state
    _instance: Optional[EnhancedBaseScanner] = field(default=None, repr=False)
    _registered_at: float = field(default_factory=time.time, repr=False)
    _enabled_changed_at: Optional[float] = field(default=None, repr=False)
    _enable_history: List[Dict[str, Any]] = field(default_factory=list, repr=False)

    def instantiate(self, config: Optional[Dict[str, Any]] = None) -> EnhancedBaseScanner:
        if self._instance is None:
            self._instance = self.scanner_cls(config or {})
        return self._instance

    def set_enabled(self, enabled: bool, reason: str = "") -> None:
        old = self.enabled
        self.enabled = enabled
        self._enabled_changed_at = time.time()
        self._enable_history.append({
            "from": old,
            "to": enabled,
            "reason": reason,
            "at": self._enabled_changed_at,
        })
        logger.info("Scanner '%s' %s (reason: %s)", self.name, "enabled" if enabled else "disabled", reason)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category.value,
            "version": self.version,
            "enabled": self.enabled,
            "description": self.description,
            "priority": self.priority.value,
            "requires_scope": self.requires_scope,
            "dependencies": self.dependencies,
            "capabilities": self.capabilities,
            "category_order": CATEGORY_ORDER.get(self.category, 999),
        }


class ScannerRegistry:
    """Central registry with dependency resolution and health checks."""

    def __init__(self) -> None:
        self._plugins: Dict[str, ScannerPlugin] = {}

    def register(self, plugin: ScannerPlugin) -> ScannerPlugin:
        if plugin.name in self._plugins:
            logger.warning("Scanner '%s' already registered; overwriting.", plugin.name)
        self._plugins[plugin.name] = plugin
        logger.debug(
            "Registered scanner '%s' v%s (%s, priority=%d)",
            plugin.name, plugin.version, plugin.category.value, plugin.priority.value,
        )
        return plugin

    def get(self, name: str) -> Optional[ScannerPlugin]:
        return self._plugins.get(name)

    def all(self) -> List[ScannerPlugin]:
        return list(self._plugins.values())

    def enabled(self) -> List[ScannerPlugin]:
        return [p for p in self._plugins.values() if p.enabled]

    def by_category(self, category: ScannerCategory) -> List[ScannerPlugin]:
        return sorted(
            [p for p in self.enabled() if p.category == category],
            key=lambda p: p.priority.value,
        )

    def set_enabled(self, name: str, enabled: bool, reason: str = "") -> bool:
        plugin = self._plugins.get(name)
        if plugin:
            plugin.set_enabled(enabled, reason)
            return True
        return False

    # --- Dependency resolution ---

    def resolve_execution_order(self, categories: Optional[List[ScannerCategory]] = None) -> List[ScannerPlugin]:
        """Return enabled plugins in topologically-sorted order respecting dependencies.

        If ``categories`` is provided, only plugins in those categories are included.
        """
        candidates = self.enabled()
        if categories:
            cat_set = set(categories)
            candidates = [p for p in candidates if p.category in cat_set]

        # Build adjacency: plugin -> set of plugin names it depends on (within candidates)
        candidate_names = {p.name for p in candidates}
        name_to_plugin = {p.name: p for p in candidates}

        # Kahn's algorithm for topological sort
        in_degree: Dict[str, int] = {n: 0 for n in candidate_names}
        dependents: Dict[str, List[str]] = {n: [] for n in candidate_names}

        for p in candidates:
            for dep in p.dependencies:
                if dep in candidate_names:
                    in_degree[p.name] += 1
                    dependents[dep].append(p.name)

        # Start with plugins that have no in-candidate dependencies
        queue = sorted(
            [n for n, d in in_degree.items() if d == 0],
            key=lambda n: (CATEGORY_ORDER.get(name_to_plugin[n].category, 999), name_to_plugin[n].priority.value),
        )

        result: List[ScannerPlugin] = []
        while queue:
            name = queue.pop(0)
            result.append(name_to_plugin[name])
            for dependent in dependents[name]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
            queue.sort(key=lambda n: (CATEGORY_ORDER.get(name_to_plugin[n].category, 999), name_to_plugin[n].priority.value))

        if len(result) != len(candidates):
            missing = candidate_names - {p.name for p in result}
            logger.error("Circular dependency detected involving: %s", missing)
            # Add remaining in priority order as fallback
            for p in sorted(candidates, key=lambda x: (CATEGORY_ORDER.get(x.category, 999), x.priority.value)):
                if p.name not in {r.name for r in result}:
                    result.append(p)

        return result

    # --- Health checks ---

    def health_all(self) -> List[Dict[str, Any]]:
        """Health status of every registered scanner."""
        results = []
        for plugin in self.enabled():
            try:
                instance = plugin.instantiate()
                health = instance.health_check()
                health["plugin"] = plugin.to_dict()
                results.append(health)
            except Exception as exc:
                results.append({
                    "name": plugin.name,
                    "healthy": False,
                    "error": str(exc),
                    "plugin": plugin.to_dict(),
                })
        return results

    # --- Manifest ---

    def manifest(self) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self.all()]


# Process-wide singleton
registry = ScannerRegistry()


def register_scanner(
    name: str,
    category: ScannerCategory,
    version: str = "1.0.0",
    enabled: bool = True,
    description: str = "",
    priority: ScannerPriority = ScannerPriority.NORMAL,
    requires_scope: bool = True,
    dependencies: Optional[List[str]] = None,
    capabilities: Optional[List[str]] = None,
):
    """Class decorator that registers a scanner subclass."""
    def decorator(cls: Type[EnhancedBaseScanner]) -> Type[EnhancedBaseScanner]:
        # Inherit metadata from class if not overridden
        plugin = ScannerPlugin(
            name=name,
            category=category,
            scanner_cls=cls,
            enabled=enabled,
            description=description or cls.description,
            version=version or cls.version,
            priority=priority or cls.priority,
            requires_scope=requires_scope,
            dependencies=dependencies or cls.dependencies,
            capabilities=capabilities or cls.capabilities,
        )
        registry.register(plugin)
        return cls
    return decorator
