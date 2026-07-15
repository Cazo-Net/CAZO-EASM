"""Celery application for background scan processing.

Using a real task queue (backed by Redis) instead of FastAPI BackgroundTasks so
that scans survive process restarts, can be retried, and scale across workers.
"""

from celery import Celery
from app.config import settings, get_celery_broker_url, get_celery_result_backend

celery_app = Celery(
    "attacksec",
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
)
