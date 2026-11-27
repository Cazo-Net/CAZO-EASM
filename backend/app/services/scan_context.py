"""Per-scan execution context shared by the scan services and the queue worker."""
from __future__ import annotations

from contextvars import ContextVar

# True while a scan runs under the durable queue worker. The worker then owns
# retries, the final "failed" status and the failure notification, so the scan
# services must not mark the scan failed (or notify) on an attempt that may be
# retried.
queue_managed: ContextVar[bool] = ContextVar("scan_queue_managed", default=False)


class ScanCancelled(Exception):
    """The scan was cancelled by a user; stop without recording a failure."""
