"""Structured logging configuration.

In production the application emits one JSON object per line so logs can be
ingested by aggregation systems (ELK, Datadog, CloudWatch, Loki, ...). In
development/test the default human-readable formatting is preserved.
"""

import json
import logging
import sys
import time
from typing import Any

from app.config import is_production

_RESERVED = {
    "args", "asctime", "created", "exc_info", "exc_text", "filename", "funcName",
    "levelname", "levelno", "lineno", "module", "msecs", "msg", "name", "pathname",
    "process", "processName", "relativeCreated", "stack_info", "thread", "threadName",
    "getMessage",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log["exception"] = self.formatException(record.exc_info)
        for key, val in record.__dict__.items():
            if key in _RESERVED or key.startswith("_"):
                continue
            if key in log:
                continue
            if isinstance(val, (str, int, float, bool)):
                log[key] = val
        return json.dumps(log, default=str)


_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    """Configure the `app.*` loggers to emit JSON in production.

    Idempotent. Only mutates logging when running in production; dev/test keeps
    the default (human-readable) formatting so test output stays readable.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    logging.getLogger().setLevel(level)

    if not is_production():
        return

    app_logger = logging.getLogger("app")
    app_logger.setLevel(level)
    app_logger.propagate = False
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    app_logger.addHandler(handler)

    # Quiet noisy third-party loggers in production.
    for noisy in ("uvicorn.access", "urllib3", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
