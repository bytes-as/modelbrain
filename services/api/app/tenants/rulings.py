"""Append-only rulings with STALE_RULING concurrency control."""

from __future__ import annotations

import time
import uuid
from typing import Any

from app.errors import ApiError
from app.graph import db
from app.graph.queries import T1, T2, T6
from app.graph.rows import as_rows


def latest_ruling_id(graph: str, deployment_id: str) -> str | None:
    for row in as_rows(db.ro_query(graph, T6)):
        # T6 does not return deployment_id; look up via a bounded query
        pass
    rows = as_rows(
        db.ro_query(
            graph,
            """
            MATCH (dep:Deployment {id: $deployment_id})<-[:FOR]-(r:Ruling)
            OPTIONAL MATCH (newer:Ruling)-[:SUPERSEDES]->(r)
            WITH r, newer WHERE newer IS NULL
            RETURN r.id AS ruling_id
            ORDER BY r.created_at DESC LIMIT 1
            """,
            {"deployment_id": deployment_id},
        )
    )
    if not rows:
        return None
    return str(rows[0].get("ruling_id") or "") or None


def write_ruling(
    graph: str,
    *,
    deployment_id: str,
    verdict: dict[str, Any],
    expected_ruling_id: str | None = None,
) -> str:
    current = latest_ruling_id(graph, deployment_id)
    if expected_ruling_id is not None and current != expected_ruling_id:
        raise ApiError(
            "STALE_RULING",
            "Someone updated this deployment a moment ago.",
            hint=f"Latest ruling is {current}.",
        )
    ruling_id = "rul_" + uuid.uuid4().hex[:12]
    now = int(time.time() * 1000)
    clause_ids = [
        hit["clause_id"]
        for hit in (
            list(verdict.get("blocking") or [])
            + list(verdict.get("obligations") or [])
            + list(verdict.get("needs_counsel") or [])
        )
    ]
    db.query(
        graph,
        T1,
        {
            "deployment_id": deployment_id,
            "ruling_id": ruling_id,
            "verdict": verdict["verdict"],
            "strict": bool(verdict.get("strict")),
            "now": now,
            "explanation": verdict.get("explanation") or "",
            "hub_sha_set": list(verdict.get("hub_sha_set") or []),
            "facts": [
                {
                    "id": "fact_" + uuid.uuid4().hex[:12],
                    "model_id": verdict["model_id"],
                    "sha": "",
                    "license_key": verdict.get("declared_license") or "",
                    "clause_ids": clause_ids,
                    "edge_tiers": [],
                }
            ],
        },
    )
    if current:
        db.query(graph, T2, {"new_id": ruling_id, "old_id": current})
        db.query(
            graph,
            """
            MATCH (old:Ruling {id: $old_id})
            CREATE (e:Event {id: $event_id, kind: 'SUPERSEDED', at: $now, reason: 'new ruling'})
            CREATE (e)-[:ON]->(old)
            """,
            {"old_id": current, "event_id": "evt_" + uuid.uuid4().hex[:12], "now": now},
        )
    return ruling_id


def decision_trace(graph: str, ruling_id: str) -> dict[str, object]:
    from app.graph.queries import T7

    rows = as_rows(db.ro_query(graph, T7, {"ruling_id": ruling_id}))
    if not rows:
        raise ApiError("MODEL_NOT_FOUND", f"No ruling '{ruling_id}'.")
    row = rows[0]
    return {
        "verdict": row.get("verdict"),
        "facts": row.get("facts") or [],
        "events": row.get("events") or [],
    }
