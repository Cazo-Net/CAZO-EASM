"""Scan worker: runs queued scans outside the web server.

Start one or more with::

    python -m app.workers.scan_worker

Each worker runs up to ``SCAN_WORKER_CONCURRENCY`` scans at once. It claims
jobs from the ``scan_jobs`` table, sends a heartbeat while each scan runs,
enforces a per-scan time limit, retries failures with backoff, and on
SIGTERM (a deploy) stops claiming work and puts unfinished jobs back in the
queue. Workers also run the periodic jobs (scheduled scans, SSL expiry,
weekly digest, CVE sync); see ``app/services/periodic.py``.

Scaling out is just running more worker processes or replicas; they
coordinate through Postgres row locks.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket
from datetime import datetime, timezone
from typing import Awaitable, Callable, Dict, Optional

from app.config import settings
from app.services import job_queue
from app.services.job_queue import ClaimedJob

logger = logging.getLogger("app.workers.scan_worker")

ScanExecutor = Callable[[ClaimedJob], Awaitable[None]]


def _session():
    # Looked up at call time so tests can swap the session factory.
    import app.database as database

    return database.SessionLocal()


def scan_timeout_seconds(scan_type: str) -> int:
    if (scan_type or "full") == "quick":
        return int(settings.SCAN_TIMEOUT_QUICK_MINUTES) * 60
    return int(settings.SCAN_TIMEOUT_FULL_MINUTES) * 60


async def default_executor(job: ClaimedJob) -> None:
    """Run the scan with the service matching the job's engine."""
    if job.engine == "v2":
        from app.services.scan_service_v2 import ScanServiceV2 as Service
    else:
        from app.services.scan_service import ScanService as Service

    db = _session()
    try:
        await Service(db).execute_scan(job.scan_id)
    finally:
        db.close()


class ScanWorker:
    def __init__(
        self,
        concurrency: Optional[int] = None,
        worker_id: Optional[str] = None,
        executor: ScanExecutor = default_executor,
        poll_interval: float = 2.0,
        run_periodic: Optional[bool] = None,
    ):
        self.concurrency = max(1, concurrency or int(settings.SCAN_WORKER_CONCURRENCY))
        self.worker_id = worker_id or f"{socket.gethostname()}-{os.getpid()}"
        self.executor = executor
        self.poll_interval = poll_interval
        self.run_periodic = settings.RUN_PERIODIC_TASKS if run_periodic is None else run_periodic
        self._running: Dict[str, asyncio.Task] = {}
        self._stopping = asyncio.Event()
        self._last_reap = 0.0
        self.started_at = datetime.now(timezone.utc)

    # ── public ────────────────────────────────────────────────────────

    def stop(self) -> None:
        self._stopping.set()

    @property
    def active_jobs(self) -> int:
        return len(self._running)

    async def run(self) -> None:
        logger.info("Scan worker %s started (concurrency=%d)", self.worker_id, self.concurrency)
        self._reap()
        try:
            while not self._stopping.is_set():
                worked = await self.tick()
                if not worked:
                    try:
                        await asyncio.wait_for(self._stopping.wait(), timeout=self.poll_interval)
                    except asyncio.TimeoutError:
                        pass
        finally:
            await self._shutdown()

    async def tick(self) -> bool:
        """One loop iteration. Returns True if a job was claimed."""
        loop = asyncio.get_running_loop()
        if loop.time() - self._last_reap > 60:
            self._reap()
        if self.run_periodic:
            await asyncio.to_thread(self._periodic)

        claimed = False
        while len(self._running) < self.concurrency and not self._stopping.is_set():
            job = await asyncio.to_thread(self._claim)
            if job is None:
                break
            claimed = True
            self._running[job.id] = asyncio.create_task(self._run_job(job), name=f"scan-{job.scan_id}")
        return claimed

    async def drain(self) -> None:
        """Wait for all running jobs (used by tests)."""
        while self._running:
            await asyncio.gather(*list(self._running.values()), return_exceptions=True)

    # ── internals ─────────────────────────────────────────────────────

    def _claim(self) -> Optional[ClaimedJob]:
        db = _session()
        try:
            return job_queue.claim_next_job(db, self.worker_id)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to claim a job")
            db.rollback()
            return None
        finally:
            db.close()

    def _reap(self) -> None:
        try:
            self._last_reap = asyncio.get_running_loop().time()
        except RuntimeError:
            pass
        db = _session()
        try:
            n = job_queue.reap_stale_jobs(db)
            if n:
                logger.warning("Recovered %d job(s) from dead workers", n)
        except Exception:  # noqa: BLE001
            logger.exception("Reaper failed")
            db.rollback()
        finally:
            db.close()

    def _periodic(self) -> None:
        from app.services.periodic import run_periodic_tasks

        db = _session()
        try:
            run_periodic_tasks(db, self.worker_id)
        except Exception:  # noqa: BLE001
            logger.exception("Periodic tasks failed")
            db.rollback()
        finally:
            db.close()

    def _preflight(self, job: ClaimedJob) -> Optional[str]:
        """Re-check scope and target right before scanning. Returns a denial reason or None."""
        from app.core.scope import authorize_scan_target

        db = _session()
        try:
            auth = authorize_scan_target(db, job.org_id or None, job.domain, auto_register=False)
            return None if auth.authorized else auth.reason
        finally:
            db.close()

    async def _heartbeat_loop(self, job: ClaimedJob, task: asyncio.Task) -> None:
        interval = max(1, int(settings.SCAN_HEARTBEAT_SECONDS))
        while not task.done():
            await asyncio.sleep(interval)
            if task.done():
                return
            db = _session()
            try:
                still_ours = job_queue.heartbeat(db, job.id, self.worker_id)
            except Exception:  # noqa: BLE001
                logger.exception("Heartbeat failed for job %s", job.id)
                db.rollback()
                still_ours = True
            finally:
                db.close()
            if not still_ours:
                logger.warning("Job %s was cancelled or reassigned; stopping scan %s", job.id, job.scan_id)
                task.cancel()
                return

    async def _run_job(self, job: ClaimedJob) -> None:
        logger.info("Running scan %s (%s, %s, attempt %d/%d) for %s",
                    job.scan_id, job.scan_type, job.engine, job.attempt + 1, job.max_attempts, job.domain)
        try:
            denial = await asyncio.to_thread(self._preflight, job)
            if denial:
                await asyncio.to_thread(self._finish_failed, job, f"Not authorized: {denial}", False)
                return

            timeout = scan_timeout_seconds(job.scan_type)
            scan_task = asyncio.create_task(asyncio.wait_for(self.executor(job), timeout=timeout))
            hb = asyncio.create_task(self._heartbeat_loop(job, scan_task))
            try:
                await scan_task
            except asyncio.TimeoutError:
                await asyncio.to_thread(
                    self._finish_failed, job, f"Scan timed out after {timeout // 60} minutes", True)
                return
            except asyncio.CancelledError:
                if self._stopping.is_set():
                    await asyncio.to_thread(self._release, job)
                else:
                    await asyncio.to_thread(self._mark_scan_cancelled, job)
                return
            except Exception as exc:  # noqa: BLE001
                await asyncio.to_thread(self._finish_failed, job, str(exc) or type(exc).__name__, True)
                return
            finally:
                hb.cancel()

            await asyncio.to_thread(self._finish_ok, job)
        except Exception:  # noqa: BLE001
            logger.exception("Unexpected error handling job %s", job.id)
        finally:
            self._running.pop(job.id, None)

    def _finish_ok(self, job: ClaimedJob) -> None:
        db = _session()
        try:
            job_queue.complete_job(db, job.id)
            logger.info("Scan %s completed", job.scan_id)
        finally:
            db.close()

    def _finish_failed(self, job: ClaimedJob, error: str, retryable: bool) -> None:
        db = _session()
        try:
            status = job_queue.fail_job(db, job, error, retryable=retryable)
            logger.warning("Scan %s failed (%s): %s", job.scan_id, status, error)
        finally:
            db.close()

    def _release(self, job: ClaimedJob) -> None:
        db = _session()
        try:
            job_queue.release_job(db, job.id, job.scan_id)
            logger.info("Released job %s back to the queue (shutdown)", job.id)
        finally:
            db.close()

    def _mark_scan_cancelled(self, job: ClaimedJob) -> None:
        from sqlalchemy import text

        db = _session()
        try:
            db.execute(
                text("UPDATE scans SET status = 'cancelled', completed_at = :now "
                     "WHERE id = :sid AND status IN ('pending', 'running')"),
                {"now": datetime.now(timezone.utc), "sid": job.scan_id},
            )
            db.commit()
        finally:
            db.close()

    async def _shutdown(self) -> None:
        if not self._running:
            return
        grace = int(os.environ.get("SCAN_WORKER_SHUTDOWN_GRACE_SECONDS", "20"))
        logger.info("Stopping: waiting up to %ds for %d running scan(s)", grace, len(self._running))
        tasks = list(self._running.values())
        _, pending = await asyncio.wait(tasks, timeout=grace)
        for t in pending:
            t.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)


# ── Embedded mode (inside the API process) ─────────────────────────────

_embedded: Optional[ScanWorker] = None
_embedded_task: Optional[asyncio.Task] = None


async def start_embedded_worker() -> None:
    global _embedded, _embedded_task
    if _embedded_task is not None:
        return
    _embedded = ScanWorker()
    _embedded_task = asyncio.create_task(_embedded.run(), name="embedded-scan-worker")


async def stop_embedded_worker() -> None:
    global _embedded, _embedded_task
    if _embedded is None or _embedded_task is None:
        return
    _embedded.stop()
    try:
        await asyncio.wait_for(_embedded_task, timeout=30)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        _embedded_task.cancel()
    _embedded, _embedded_task = None, None


def embedded_worker() -> Optional[ScanWorker]:
    return _embedded


# ── CLI entry point ────────────────────────────────────────────────────


async def _main() -> None:
    from app.core.logging import configure_logging

    configure_logging(getattr(settings, "LOG_LEVEL", "INFO"))
    worker = ScanWorker()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, worker.stop)
        except NotImplementedError:  # Windows
            pass
    await worker.run()
    logger.info("Scan worker %s stopped", worker.worker_id)


if __name__ == "__main__":
    asyncio.run(_main())
