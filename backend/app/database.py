from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator
from app.config import settings, get_database_url, normalize_postgres_url
import logging

logger = logging.getLogger("app.database")

# ---------------------------------------------------------------------------
# Write engine (primary) — production-grade pooling for 1M+ users
# ---------------------------------------------------------------------------
_write_engine_kwargs = {
    "echo": settings.DATABASE_ECHO,
}

if settings.USE_SQLITE:
    _write_engine_kwargs["connect_args"] = {"check_same_thread": False}
    # Make sure the directory for a file-based SQLite DB exists (fresh checkouts
    # and CI have no ./data directory, which made every DB call fail).
    _sqlite_path = get_database_url().split("sqlite:///", 1)[-1]
    if _sqlite_path and _sqlite_path != ":memory:":
        import os as _os
        _os.makedirs(_os.path.dirname(_os.path.abspath(_sqlite_path)), exist_ok=True)
else:
    _write_engine_kwargs.update({
        "pool_pre_ping": settings.DB_POOL_PRE_PING,
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        "pool_recycle": settings.DB_POOL_RECYCLE,
        # SQLAlchemy's compiled-statement cache (client side). Note: psycopg2
        # has no server-side prepared statement cache, and Postgres rejects
        # unknown "-c" startup options, so nothing is passed via connect_args.
        "query_cache_size": settings.DB_STATEMENT_CACHE_SIZE,
    })

write_engine = create_engine(get_database_url(), **_write_engine_kwargs)

# ---------------------------------------------------------------------------
# Read engine (optional replica) — routes all SELECT queries to replica
# ---------------------------------------------------------------------------
_read_engine = None
if settings.DATABASE_READ_URL and not settings.USE_SQLITE:
    _read_engine_kwargs = {
        "echo": settings.DATABASE_ECHO,
        "pool_pre_ping": settings.DB_POOL_PRE_PING,
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_timeout": settings.DB_POOL_TIMEOUT,
        "pool_recycle": settings.DB_POOL_RECYCLE,
        "query_cache_size": settings.DB_STATEMENT_CACHE_SIZE,
    }
    _read_engine = create_engine(normalize_postgres_url(settings.DATABASE_READ_URL), **_read_engine_kwargs)
    logger.info("Read replica configured: %s", settings.DATABASE_READ_URL.split("@")[-1])


def _get_engine(read_only: bool = False):
    """Return the appropriate engine — read replica when available for reads."""
    if read_only and _read_engine is not None:
        return _read_engine
    return write_engine


# ---------------------------------------------------------------------------
# Session factory — supports read/write split
# ---------------------------------------------------------------------------
WriteSession = sessionmaker(autocommit=False, autoflush=False, bind=write_engine)

if _read_engine:
    ReadSession = sessionmaker(autocommit=False, autoflush=False, bind=_read_engine)
else:
    ReadSession = WriteSession

Base = declarative_base()

# ---------------------------------------------------------------------------
# Backward-compat alias — existing code imports `SessionLocal`
# ---------------------------------------------------------------------------
SessionLocal = WriteSession


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — write session (default)."""
    db = WriteSession()
    try:
        yield db
    finally:
        db.close()


def get_read_db() -> Generator[Session, None, None]:
    """FastAPI dependency — read-only session (routes to replica if available)."""
    db = ReadSession()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context(read_only: bool = False) -> Generator[Session, None, None]:
    """Context manager for non-FastAPI code (tasks, scripts, etc.)."""
    session_cls = ReadSession if read_only else WriteSession
    db = session_cls()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """Initialize database tables.

    Creates all tables defined on the declarative Base. ``create_all`` is
    idempotent: it only creates tables that do not already exist, so it is
    safe to run in every environment (dev, prod, and alongside Alembic).
    """
    from app import models  # noqa: F401  (registers all tables on Base.metadata)
    Base.metadata.create_all(bind=write_engine)
