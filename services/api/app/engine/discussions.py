"""Hugging Face discussions as graph memory (G087, FLOWS F11).

Discussions about watched models become (:Discussion)-[:ABOUT]->(:Model). The Xkev licence
thread gets its real Outcome (FIXED after 130 days), so the graph remembers how long an
upstream fix took and which children never received it.
"""

from __future__ import annotations

import logging
from typing import Any

from app.graph import db
from app.graph.queries import X18, X19, X20
from app.graph.rows import as_rows

log = logging.getLogger("modelbrain.discussions")
HUB = "https://huggingface.co"


async def ingest_discussions(
    client: Any, model_id: str, graph: str = "hub", limit: int = 50
) -> int:
    payload = await client.get_json(f"{HUB}/api/models/{model_id}/discussions")
    items = payload.get("discussions", []) if isinstance(payload, dict) else []
    written = 0
    for item in items[:limit]:
        if not isinstance(item, dict) or "num" not in item:
            continue
        num = int(item["num"])
        key = f"{model_id}#{num}"
        url = f"{HUB}/{model_id}/discussions/{num}"
        rows = as_rows(
            db.query(
                graph,
                X18,
                {
                    "model_id": model_id,
                    "key": key,
                    "num": num,
                    "title": str(item.get("title") or "")[:200],
                    "status": str(item.get("status") or ""),
                    "opened_at": str(item.get("createdAt") or ""),
                    "is_pr": bool(item.get("isPullRequest")),
                    "url": url,
                },
            )
        )
        written += len(rows)
    return written


def record_outcome(
    model_id: str,
    num: int,
    *,
    kind: str,
    days: int,
    observed_at: str,
    evidence_url: str,
    graph: str = "hub",
) -> bool:
    key = f"{model_id}#{num}"
    outcome_id = f"outcome:{key}"
    rows = as_rows(
        db.query(
            graph,
            X19,
            {
                "key": key,
                "id": outcome_id,
                "kind": kind,
                "days": days,
                "observed_at": observed_at,
                "evidence_url": evidence_url,
            },
        )
    )
    return bool(rows)


def discussions_for(model_id: str, graph: str = "hub") -> list[dict[str, Any]]:
    return as_rows(db.ro_query(graph, X20, {"model_id": model_id}))
