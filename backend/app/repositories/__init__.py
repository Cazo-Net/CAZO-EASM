"""Repository package.

A growing set of data-access modules that encapsulate ORM queries behind
typed, testable functions. Routers and services should prefer these over
scattering ``db.query(...)`` calls, which improves testability and keeps
query logic in one place.
"""
from app.repositories.assets import (
    upsert_asset,
    upsert_relationship,
    get_asset_graph,
    backfill_from_scan,
)

__all__ = [
    "upsert_asset",
    "upsert_relationship",
    "get_asset_graph",
    "backfill_from_scan",
]
