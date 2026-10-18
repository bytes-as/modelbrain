"""Alternatives for BLOCKED verdicts from cached hub data only (FLOWS F1.9)."""

from __future__ import annotations

import json
from typing import Any

from app.engine.verdict import decide
from app.graph import db
from app.graph.queries import C3, Q1, Q2
from app.graph.rows import as_rows
from app.paths import repo_root

NO_ALTERNATIVE = "No compliant alternative in our candidate set"


def candidate_ids(pipeline_tag: str | None) -> list[str]:
    payload = json.loads((repo_root() / "data" / "alternatives.json").read_text())
    tag = pipeline_tag or "text-generation"
    ids = list(payload.get(tag) or [])
    if not ids:
        ids = list(payload.get("text-generation") or [])
    return ids[:8]


def find_alternatives(
    context: dict[str, Any],
    *,
    graph: str,
    min_tier: int,
    pipeline_tag: str | None,
    exclude: str,
) -> tuple[list[dict[str, str]], str | None]:
    """Return (alternatives, message_if_empty). Never triggers ingest."""
    found: list[dict[str, str]] = []
    for model_id in candidate_ids(pipeline_tag):
        if model_id == exclude:
            continue
        props = as_rows(db.ro_query(graph, C3, {"model_id": model_id}))
        if not props:
            continue
        q1 = as_rows(db.ro_query(graph, Q1, {"model_id": model_id, "min_tier": min_tier}))
        q2 = as_rows(db.ro_query(graph, Q2, {"model_id": model_id, "min_tier": min_tier}))
        decided = decide(model_id, q1, q2, context, props[0])
        if decided["verdict"] in ("ALLOWED", "ALLOWED_WITH_OBLIGATIONS"):
            found.append({"model_id": model_id, "verdict": decided["verdict"]})
    if found:
        return found, None
    return [], NO_ALTERNATIVE
