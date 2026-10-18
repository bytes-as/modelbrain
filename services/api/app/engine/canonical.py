"""Merge alias nodes left by renamed Hub repos into their canonical node (G147)."""

from __future__ import annotations

import logging
from typing import Any

from app.agents.scout import canonical_id
from app.graph import db
from app.graph.queries import W13, X7, X8, X9, X10
from app.graph.rows import as_rows

log = logging.getLogger("modelbrain.canonical")


async def merge_aliases(source: Any, graph: str = "hub") -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    targets = [str(r["id"]) for r in as_rows(db.ro_query(graph, X10))]
    for alias in targets:
        canonical = await canonical_id(source, alias)
        if canonical == alias:
            continue
        exists = as_rows(db.ro_query(graph, W13, {"ids": [canonical]}))
        if not exists:
            log.info("canonical node missing; keeping alias", extra={"alias": alias})
            continue
        for row in as_rows(db.ro_query(graph, X7, {"alias": alias})):
            if str(row["child"]) == canonical:
                continue
            db.query(
                graph, X8, {"child": row["child"], "canonical": canonical, "props": row["props"]}
            )
        db.query(graph, X9, {"alias": alias, "canonical": canonical})
        merged.append({"alias": alias, "canonical": canonical})
        log.info("alias merged", extra={"alias": alias, "canonical": canonical})
    return merged
