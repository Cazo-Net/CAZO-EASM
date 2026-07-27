"""Upstash managed services client.

Provides lazy-initialized, singleton clients for:
- Upstash Redis (rate limiting, caching, sessions)
- Upstash QStash (reliable task queue, replaces BackgroundTasks)
- Upstash Kafka (event streaming)

All clients gracefully degrade to no-ops when credentials are not configured.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from app.config import settings

logger = logging.getLogger("app.services.upstash")

# ---------------------------------------------------------------------------
# Upstash Redis
# ---------------------------------------------------------------------------
_redis_client = None


def get_upstash_redis():
    """Return an Upstash Redis client, or None if not configured."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if not settings.UPSTASH_REDIS_URL:
        return None
    try:
        from upstash_redis import Redis
        _redis_client = Redis(url=settings.UPSTASH_REDIS_URL, token=settings.UPSTASH_REDIS_TOKEN)
        logger.info("Upstash Redis connected (%s…)", settings.UPSTASH_REDIS_URL[:30])
        return _redis_client
    except Exception as exc:
        logger.warning("Upstash Redis init failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Upstash QStash (task queue)
# ---------------------------------------------------------------------------
_qstash_client = None


def get_qstash_client():
    """Return a QStash client, or None if not configured."""
    global _qstash_client
    if _qstash_client is not None:
        return _qstash_client
    if not settings.QSTASH_TOKEN:
        return None
    try:
        from qstash import QStash
        _qstash_client = QStash(settings.QSTASH_TOKEN)
        logger.info("QStash client initialized")
        return _qstash_client
    except Exception as exc:
        logger.warning("QStash init failed: %s", exc)
        return None


async def publish_task(
    url: str,
    payload: dict,
    retries: int = 3,
    retry_delay: str = "30s",
    headers: Optional[dict] = None,
) -> Optional[str]:
    """Publish a task to QStash. Returns message ID or None."""
    client = get_qstash_client()
    if not client:
        logger.debug("QStash not configured, skipping task publish to %s", url)
        return None
    try:
        result = client.message.publish_json(
            url=url,
            body=payload,
            retries=retries,
            retry_delay=retry_delay,
            headers=headers or {},
        )
        msg_id = getattr(result, "message_id", None) or str(result)
        logger.info("QStash task published: %s -> %s", url, msg_id)
        return msg_id
    except Exception as exc:
        logger.error("QStash publish failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Upstash Kafka (event streaming)
# ---------------------------------------------------------------------------
_kafka_producer = None


def get_kafka_producer():
    """Return a Kafka producer (works with Upstash Kafka), or None if not configured."""
    global _kafka_producer
    if _kafka_producer is not None:
        return _kafka_producer
    if not settings.UPSTASH_KAFKA_URL:
        return None
    try:
        from kafka import KafkaProducer
        _kafka_producer = KafkaProducer(
            bootstrap_servers=settings.UPSTASH_KAFKA_URL,
            security_protocol="SASL_SSL",
            sasl_mechanism="PLAIN",
            sasl_plain_username=settings.UPSTASH_KAFKA_USERNAME,
            sasl_plain_password=settings.UPSTASH_KAFKA_PASSWORD,
            value_serializer=lambda v: v.encode("utf-8") if isinstance(v, str) else v,
        )
        logger.info("Upstash Kafka producer connected")
        return _kafka_producer
    except ImportError:
        logger.warning("kafka-python not installed; Kafka producer unavailable")
        return None
    except Exception as exc:
        logger.warning("Upstash Kafka init failed: %s", exc)
        return None


async def publish_event(topic: str, key: str, value: str) -> bool:
    """Publish an event to Kafka. Returns True on success."""
    producer = get_kafka_producer()
    if not producer:
        logger.debug("Kafka not configured, skipping event to topic=%s", topic)
        return False
    try:
        producer.send(topic, key=key, value=value)
        producer.flush(timeout=5)
        return True
    except Exception as exc:
        logger.error("Kafka publish failed (topic=%s): %s", topic, exc)
        return False
