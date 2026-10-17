"""Apply SCHEMA to the hub and any existing tenant graphs. Index creation is idempotent."""

from __future__ import annotations

import logging

from app.graph.db import _database, query
from app.graph.queries import SCHEMA

log = logging.getLogger("modelbrain.schema")


def statements(block: str) -> list[str]:
    return [part.strip() for part in block.split(";") if part.strip()]


def graph_names() -> list[str]:
    names = {str(name) for name in _database().list_graphs()}
    names.add("hub")
    tenants = sorted(name for name in names if name.startswith(("tenant_", "sbx_")))
    return ["hub", *tenants]


def apply_schema() -> None:
    for name in graph_names():
        for statement in statements(SCHEMA):
            try:
                query(name, statement)
            except Exception as exc:
                if "already indexed" in str(exc).lower():
                    continue
                raise
        log.info("schema applied on %s", name)
