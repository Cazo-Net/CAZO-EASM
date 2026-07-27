"""Enhanced base scanner with metrics, circuit breaker, and structured logging.

Every scanner in the v2 engine inherits from EnhancedBaseScanner which provides:
- Configurable timeout, retry with exponential backoff
- Circuit breaker pattern (opens after N consecutive failures)
- Structured metrics collection (duration, success rate, error counts)
- Standardized result format with normalization hooks
- Dependency declaration for pipeline ordering
"""
from __future__ import annotations

import asyncio
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & data classes
# ---------------------------------------------------------------------------

class ScannerPriority(int, Enum):
    """Execution priority — lower runs first."""
    CRITICAL = 10
    HIGH = 20
    NORMAL = 50
    LOW = 80
    BACKGROUND = 100


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ScannerMetrics:
    """Accumulated metrics for a single scanner instance."""
    total_runs: int = 0
    successes: int = 0
    failures: int = 0
    timeouts: int = 0
    total_duration_ms: float = 0.0
    min_duration_ms: float = float("inf")
    max_duration_ms: float = 0.0
    consecutive_failures: int = 0
    last_success_at: Optional[float] = None
    last_failure_at: Optional[float] = None

    @property
    def avg_duration_ms(self) -> float:
        return self.total_duration_ms / self.total_runs if self.total_runs else 0.0

    @property
    def success_rate(self) -> float:
        return self.successes / self.total_runs if self.total_runs else 0.0

    def record_success(self, duration_ms: float) -> None:
        self.total_runs += 1
        self.successes += 1
        self.consecutive_failures = 0
        self.total_duration_ms += duration_ms
        self.min_duration_ms = min(self.min_duration_ms, duration_ms)
        self.max_duration_ms = max(self.max_duration_ms, duration_ms)
        self.last_success_at = time.time()

    def record_failure(self, duration_ms: float) -> None:
        self.total_runs += 1
        self.failures += 1
        self.consecutive_failures += 1
        self.total_duration_ms += duration_ms
        self.last_failure_at = time.time()

    def record_timeout(self, duration_ms: float) -> None:
        self.timeouts += 1
        self.record_failure(duration_ms)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_runs": self.total_runs,
            "successes": self.successes,
            "failures": self.failures,
            "timeouts": self.timeouts,
            "success_rate": round(self.success_rate, 4),
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "min_duration_ms": round(self.min_duration_ms, 2) if self.min_duration_ms != float("inf") else 0,
            "max_duration_ms": round(self.max_duration_ms, 2),
            "consecutive_failures": self.consecutive_failures,
        }


@dataclass
class CircuitBreaker:
    """Simple circuit breaker: CLOSED → OPEN (after failures) → HALF_OPEN → CLOSED."""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0  # seconds before OPEN → HALF_OPEN
    state: CircuitState = CircuitState.CLOSED
    _opened_at: float = 0.0

    def record_success(self) -> None:
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self._open()
        elif self.state == CircuitState.CLOSED:
            # Count is managed externally via consecutive_failures
            pass

    def should_allow(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.HALF_OPEN:
            return True  # Allow one probe request
        # OPEN — check recovery timeout
        if time.time() - self._opened_at >= self.recovery_timeout:
            self.state = CircuitState.HALF_OPEN
            return True
        return False

    def open_if_threshold(self, consecutive_failures: int) -> None:
        if consecutive_failures >= self.failure_threshold:
            self._open()

    def _open(self) -> None:
        self.state = CircuitState.OPEN
        self._opened_at = time.time()
        logger.warning("Circuit breaker OPEN — pausing scanner for %.1fs", self.recovery_timeout)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }


@dataclass
class ScanResult:
    """Standardized result from any scanner."""
    success: bool
    scanner: str
    target: str
    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "success": self.success,
            "scanner": self.scanner,
            "target": self.target,
            "duration_ms": round(self.duration_ms, 2),
            "data": self.data,
            "metadata": self.metadata,
        }
        if self.errors:
            d["errors"] = self.errors
        if self.warnings:
            d["warnings"] = self.warnings
        return d


# ---------------------------------------------------------------------------
# Enhanced base scanner
# ---------------------------------------------------------------------------

class EnhancedBaseScanner(ABC):
    """Abstract base for all v2 scanners.

    Subclasses MUST implement:
        - ``scan(target, **kwargs)`` → ``ScanResult``
        - ``validate_target(target)`` → ``bool``

    Subclasses SHOULD override:
        - ``name`` (human-readable scanner name)
        - ``version`` (semver string)
        - ``category`` (from ``ScannerCategory``)
        - ``priority`` (from ``ScannerPriority``)
        - ``dependencies`` (list of scanner names that must run first)
        - ``capabilities`` (what this scanner can detect)
    """

    name: str = "base"
    version: str = "1.0.0"
    category: str = "unknown"
    priority: ScannerPriority = ScannerPriority.NORMAL
    description: str = ""
    dependencies: List[str] = []
    capabilities: List[str] = []

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.timeout: float = self.config.get("timeout", 10)
        self.max_retries: int = self.config.get("max_retries", 1)
        self.retry_base_delay: float = self.config.get("retry_base_delay", 0.5)
        self.metrics = ScannerMetrics()
        self._circuit = CircuitBreaker(
            failure_threshold=self.config.get("circuit_breaker_threshold", 5),
            recovery_timeout=self.config.get("circuit_breaker_recovery", 60.0),
        )

    # --- Abstract interface ---

    @abstractmethod
    async def scan(self, target: str, **kwargs) -> ScanResult:
        """Execute the scan against ``target`` and return a ``ScanResult``."""
        ...

    @abstractmethod
    def validate_target(self, target: str) -> bool:
        """Return True if ``target`` is a valid input for this scanner."""
        ...

    # --- Execution with retry, timeout, circuit breaker ---

    async def run(self, target: str, **kwargs) -> ScanResult:
        """Execute scan with retry, timeout, circuit breaker, and metrics."""
        if not self._circuit.should_allow():
            return ScanResult(
                success=False,
                scanner=self.name,
                target=target,
                errors=[f"Circuit breaker OPEN — scanner {self.name} temporarily disabled"],
                metadata={"circuit_breaker": self._circuit.to_dict()},
            )

        if not self.validate_target(target):
            return ScanResult(
                success=False,
                scanner=self.name,
                target=target,
                errors=[f"Invalid target: {target}"],
            )

        last_error: Optional[str] = None
        for attempt in range(self.max_retries + 1):
            start = time.monotonic()
            try:
                result = await asyncio.wait_for(
                    self.scan(target, **kwargs),
                    timeout=self.timeout,
                )
                elapsed = (time.monotonic() - start) * 1000
                result.duration_ms = elapsed
                result.metadata["attempt"] = attempt + 1
                self.metrics.record_success(elapsed)
                self._circuit.record_success()
                self._circuit.open_if_threshold(self.metrics.consecutive_failures)
                return result

            except asyncio.TimeoutError:
                elapsed = (time.monotonic() - start) * 1000
                last_error = f"Timeout after {self.timeout}s"
                self.metrics.record_timeout(elapsed)
                logger.warning(
                    "%s timeout on %s (attempt %d/%d)",
                    self.name, target, attempt + 1, self.max_retries + 1,
                )

            except Exception as exc:
                elapsed = (time.monotonic() - start) * 1000
                last_error = f"{type(exc).__name__}: {exc}"
                self.metrics.record_failure(elapsed)
                logger.warning(
                    "%s error on %s (attempt %d/%d): %s",
                    self.name, target, attempt + 1, self.max_retries + 1, last_error,
                )

            # Exponential backoff
            if attempt < self.max_retries:
                delay = self.retry_base_delay * (2 ** attempt)
                await asyncio.sleep(delay)

        # All retries exhausted
        self._circuit.open_if_threshold(self.metrics.consecutive_failures)
        return ScanResult(
            success=False,
            scanner=self.name,
            target=target,
            errors=[f"Failed after {self.max_retries + 1} attempts: {last_error}"],
            metadata={
                "attempts": self.max_retries + 1,
                "circuit_breaker": self._circuit.to_dict(),
            },
        )

    # --- Helpers ---

    def normalize_result(self, raw_data: Dict[str, Any], target: str) -> ScanResult:
        """Convenience: wrap raw data into a ScanResult."""
        return ScanResult(
            success=True,
            scanner=self.name,
            target=target,
            data=raw_data,
        )

    def format_error(self, error: Exception, target: str = "") -> ScanResult:
        """Convenience: wrap an error into a failed ScanResult."""
        return ScanResult(
            success=False,
            scanner=self.name,
            target=target,
            errors=[f"{type(error).__name__}: {error}"],
        )

    def health_check(self) -> Dict[str, Any]:
        """Return scanner health status for monitoring."""
        return {
            "name": self.name,
            "version": self.version,
            "category": self.category,
            "enabled": True,
            "metrics": self.metrics.to_dict(),
            "circuit_breaker": self._circuit.to_dict(),
        }
