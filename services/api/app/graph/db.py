"""FalkorDB connection. Read and write helpers are completed in G010."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from falkordb import FalkorDB

log = logging.getLogger("modelbrain.graph")

_db: FalkorDB | None = None


def _client() -> FalkorDB:
    password = os.environ.get("FALKORDB_PASSWORD") or None
    return FalkorDB(
        host=os.environ.get("FALKORDB_HOST", "localhost"),
        port=int(os.environ.get("FALKORDB_PORT", "6379")),
        password=password,
    )


def connect(tries: int = 10, delay_s: float = 2.0) -> FalkorDB:
    """Ping FalkorDB, retrying so a slow container start still comes up."""
    global _db
    last: Exception | None = None
    for attempt in range(1, tries + 1):
        try:
            db = _client()
            db.connection.ping()
            _db = db
            log.info("falkordb connected on attempt %s", attempt)
            return db
        except Exception as exc:
            last = exc
            log.warning("falkordb connect attempt %s failed: %s", attempt, type(exc).__name__)
            if attempt < tries:
                time.sleep(delay_s)
    assert last is not None
    raise last


def health_snapshot() -> dict[str, Any]:
    db = _db
    if db is None:
        try:
            db = connect(tries=1, delay_s=0)
        except Exception:
            return {"falkordb": "down", "graphs": [], "hub_models": 0}
    try:
        db.connection.ping()
        graphs = [str(name) for name in db.list_graphs()]
        hub_models = 0
        if "hub" in graphs:
            result = db.select_graph("hub").ro_query("MATCH (m:Model) RETURN count(m)")
            rows = result.result_set or []
            if rows:
                hub_models = int(rows[0][0])
        return {"falkordb": "up", "graphs": graphs, "hub_models": hub_models}
    except Exception as exc:
        log.warning("falkordb health check failed: %s", type(exc).__name__)
        return {"falkordb": "down", "graphs": [], "hub_models": 0}
