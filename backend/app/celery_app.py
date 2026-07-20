"""Celery application for background scan processing.

Using a real task queue (backed by Redis) instead of FastAPI BackgroundTasks so
that scans survive process restarts, can be retried, and scale across workers.
"""

from celery import Celery
from app.config import settings, get_celery_broker_url, get_celery_result_backend

celery_app = Celery(
    "cazo",
    broker=get_celery_broker_url(),
    backend=get_celery_result_backend(),
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.SCAN_TIMEOUT + 120,
    task_soft_time_limit=settings.SCAN_TIMEOUT + 60,
    worker_max_tasks_per_child=50,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "check-ssl-expiry-daily": {
            "task": "app.tasks.check_ssl_expiry",
            "schedule": {"hour": 6, "minute": 0},  # Every day at 06:00 UTC
        },
        "weekly-security-digest": {
            "task": "app.tasks.send_weekly_digest",
            "schedule": {"day_of_week": "monday", "hour": 8, "minute": 0},  # Monday 08:00 UTC
        },
        "sync-cve-database-weekly": {
            "task": "app.tasks.sync_cve_database",
            "schedule": {"day_of_week": "sunday", "hour": 3, "minute": 0},  # Sunday 03:00 UTC
        },
    },
)
