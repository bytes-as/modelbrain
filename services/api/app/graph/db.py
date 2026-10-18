"""FalkorDB connection, parameterised query helpers, and GRAPH.COPY."""

from __future__ import annotations

import logging
import time
from typing import Any

from falkordb import FalkorDB

from app.config import get_settings

log = logging.getLogger("modelbrain.graph")

_db: FalkorDB | None = None


def _client() -> FalkorDB:
    settings = get_settings()
    password = settings.falkordb_password or None
    return FalkorDB(
        host=settings.falkordb_host,
        port=settings.falkordb_port,
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


def _database() -> FalkorDB:
    if _db is None:
        return connect()
    return _db


def graph(name: str):
    return _database().select_graph(name)


def _statements(cypher: str) -> list[str]:
    return [part.strip() for part in cypher.split(";") if part.strip()]


def query(name: str, cypher: str, params: dict[str, Any] | None = None):
    """Run one copied query. A trailing semicolon is its own empty statement in FalkorDB."""
    last = None
    for statement in _statements(cypher):
        last = graph(name).query(statement, params or {})
    return last


def ro_query(name: str, cypher: str, params: dict[str, Any] | None = None):
    last = None
    for statement in _statements(cypher):
        last = graph(name).ro_query(statement, params or {})
    return last


def copy_graph(source: str, destination: str) -> None:
    """GRAPH.COPY. FalkorDB rejects the command when the destination already exists."""
    _database().connection.execute_command("GRAPH.COPY", source, destination)


def list_graphs() -> list[str]:
    return [str(name) for name in _database().list_graphs()]


def delete_graph(name: str) -> None:
    _database().connection.execute_command("GRAPH.DELETE", name)


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
