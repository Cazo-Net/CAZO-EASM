"""Per-request facts (client IP, user agent, request id) for code that has no
``Request`` object in hand, such as the audit log writer.

The request-logging middleware fills this in at the start of each request.
Outside a request (workers, scripts) every value is ``None``.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RequestContext:
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None


_EMPTY = RequestContext()
_current: ContextVar[RequestContext] = ContextVar("request_context", default=_EMPTY)


def set_request_context(ip_address: Optional[str], user_agent: Optional[str], request_id: Optional[str]):
    return _current.set(RequestContext(ip_address, user_agent, request_id))


def reset_request_context(token) -> None:
    _current.reset(token)


def get_request_context() -> RequestContext:
    return _current.get()
