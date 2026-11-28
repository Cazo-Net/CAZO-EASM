"""Bring the database schema up to date, safely, from any starting point.

Run with ``python -m app.db_migrate`` (the container entrypoint does this
before starting the API, unless ``SKIP_MIGRATIONS=true``).

Databases in the wild were built three different ways: by Alembic, by
``Base.metadata.create_all`` (the old Dockerfile and ``init_db``), or by a mix
of both. This command handles all of them:

* **Empty database** → ``create_all`` from the current models, then stamp the
  Alembic head. (Replaying every historical migration is slower and some
  early migrations do not match today's models.)
* **Managed by Alembic** → ``alembic upgrade head``.
* **Built by create_all, never stamped** → stamp the last revision before the
  queue/scope migration, then ``alembic upgrade head`` so that migration's
  idempotent column additions still apply.

After that it always runs ``create_all`` (adds any table no migration covers)
and adds model columns that are missing from existing tables. It never drops
or alters columns. On Postgres the whole run holds a transaction-scoped
advisory lock, so several replicas starting at once do not race.

Failures exit non-zero instead of being swallowed.
"""
from __future__ import annotations

import logging
import os
import sys

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.schema import CreateColumn

logger = logging.getLogger("app.db_migrate")

# Arbitrary constant used as the Postgres advisory-lock key for migrations.
_MIGRATION_LOCK_KEY = 0x0CA20EA5

# Revisions to stamp an unmanaged (create_all-built) database at, so that the
# idempotent merge migration (q5r6s7t8u9v0) still runs on top of it.
_PRE_QUEUE_HEADS = ("add_engine_col001", "p4q5r6s7t8u9")

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _alembic_config():
    from alembic.config import Config

    cfg = Config(os.path.join(_BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(_BACKEND_DIR, "alembic"))
    return cfg


def _add_missing_columns(conn: Connection, metadata) -> list[str]:
    """Add model columns missing from existing tables (never drops or alters)."""
    insp = inspect(conn)
    existing_tables = set(insp.get_table_names())
    added: list[str] = []
    for table in metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        have = {c["name"] for c in insp.get_columns(table.name)}
        for column in table.columns:
            if column.name in have or column.primary_key:
                continue
            col_sql = str(CreateColumn(column).compile(dialect=conn.dialect))
            # A NOT NULL column without a server default cannot be added to a
            # table that already has rows; add it as nullable instead.
            if not column.nullable and column.server_default is None:
                col_sql = col_sql.replace(" NOT NULL", "")
            conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN {col_sql}'))
            added.append(f"{table.name}.{column.name}")
    return added


def migrate() -> None:
    from alembic import command

    from app.database import Base, write_engine
    from app import models  # noqa: F401  (registers every table on Base.metadata)

    is_postgres = write_engine.dialect.name == "postgresql"
    cfg = _alembic_config()

    with write_engine.connect() as lock_conn:
        if is_postgres:
            # Transaction-scoped lock held by an open transaction on this
            # connection: released on commit, and safe behind PgBouncer in
            # transaction-pooling mode (a session lock would not be).
            lock_conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _MIGRATION_LOCK_KEY})
        try:
            insp = inspect(write_engine)
            tables = set(insp.get_table_names()) - {"alembic_version"}
            managed = insp.has_table("alembic_version")
            if managed:
                with write_engine.connect() as c:
                    managed = c.execute(text("SELECT COUNT(*) FROM alembic_version")).scalar() > 0

            if not tables:
                logger.info("Empty database: creating schema from models and stamping head")
                Base.metadata.create_all(bind=write_engine)
                command.stamp(cfg, "heads")
            elif managed:
                logger.info("Alembic-managed database: upgrading to head")
                try:
                    command.upgrade(cfg, "heads")
                except (ProgrammingError, OperationalError) as exc:
                    if "already exists" not in str(exc).lower():
                        raise
                    # The version table says "old revision" but later tables
                    # were already built by create_all (the old startup path
                    # did both). Replaying those migrations cannot work, so
                    # treat the schema as create_all-built: fill gaps from the
                    # models, mark the history as applied, then run only the
                    # idempotent queue/scope migration.
                    logger.warning(
                        "Alembic history does not match the schema (%s). "
                        "Reconciling from the models instead of replaying old migrations.",
                        str(exc).splitlines()[0],
                    )
                    Base.metadata.create_all(bind=write_engine)
                    command.stamp(cfg, list(_PRE_QUEUE_HEADS), purge=True)
                    command.upgrade(cfg, "heads")
            else:
                logger.info("Unmanaged (create_all) database: stamping and upgrading")
                Base.metadata.create_all(bind=write_engine)
                command.stamp(cfg, list(_PRE_QUEUE_HEADS))
                command.upgrade(cfg, "heads")

            # Tables that no migration creates, and columns added to models
            # after a table was first created.
            Base.metadata.create_all(bind=write_engine)
            with write_engine.begin() as conn:
                added = _add_missing_columns(conn, Base.metadata)
            for name in added:
                logger.warning("Added missing column %s", name)
            logger.info("Database schema is up to date")
        finally:
            if is_postgres:
                lock_conn.commit()  # releases the advisory lock


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        migrate()
    except Exception:  # noqa: BLE001
        logger.exception("Database migration failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
