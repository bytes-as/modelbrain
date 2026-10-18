"""Model lineage and descendants (G028)."""

from __future__ import annotations

import re

from fastapi import APIRouter, Query

from app.errors import ApiError
from app.graph.db import ro_query
from app.graph.queries import D1, D2, Q3, X32
from app.graph.rows import as_rows

router = APIRouter()

MODEL_ID = re.compile(r"^[\w.-]+/[\w.-]+$")


def _model_id(owner: str, name: str) -> str:
    model_id = f"{owner}/{name}"
    if not MODEL_ID.match(model_id):
        raise ApiError(
            "INVALID_INPUT",
            "Model id must look like owner/name.",
            hint="Example: meta-llama/Llama-3.2-1B.",
        )
    return model_id


SEARCH = re.compile(r"^[\w./-]{2,80}$")


@router.get("/api/models/search")
def search_models(
    q: str = Query(..., min_length=2, max_length=80),
    limit: int = Query(8, ge=1, le=20),
) -> list[dict[str, object]]:
    """Autocomplete over models already in the hub (they answer from the warm graph)."""
    term = q.strip().lower()
    if not SEARCH.match(term):
        raise ApiError(
            "INVALID_INPUT",
            "Search with letters, digits, '.', '_', '-' or '/'.",
            hint="Example: llama-3.2",
        )
    return as_rows(ro_query("hub", X32, {"q": term, "limit": limit}))


@router.get("/api/models/{owner}/{name}/lineage")
def model_lineage(
    owner: str,
    name: str,
    min_tier: int = Query(1, ge=0, le=4),
) -> dict[str, object]:
    model_id = _model_id(owner, name)
    rows = as_rows(ro_query("hub", Q3, {"model_id": model_id, "min_tier": min_tier}))
    if not rows:
        exists = as_rows(
            ro_query("hub", "MATCH (m:Model {id: $id}) RETURN m.id AS id", {"id": model_id})
        )
        if not exists:
            raise ApiError(
                "MODEL_NOT_FOUND",
                f"No model '{model_id}' in the hub.",
                hint="Ingest it first or wait for prewarm.",
            )
        return {"nodes": [], "edges": []}
    node_ids: set[str] = {model_id}
    edges: list[dict[str, object]] = []
    for row in rows:
        child = str(row.get("child") or "")
        parent = str(row.get("parent") or "")
        node_ids.add(child)
        node_ids.add(parent)
        edges.append(
            {
                "child": child,
                "parent": parent,
                "relation": row.get("relation"),
                "source": row.get("source"),
                "tier": row.get("tier"),
                "conf": row.get("conf"),
                "evidence": row.get("evidence") or "",
            }
        )
    props = as_rows(
        ro_query(
            "hub",
            """
            MATCH (m:Model)
            WHERE m.id IN $ids
            RETURN m.id AS id, m.declared_license AS declared_license,
                   coalesce(m.is_root, false) AS is_root, coalesce(m.multimodal, false) AS multimodal
            """,
            {"ids": list(node_ids)},
        )
    )
    nodes = [
        {
            "id": row["id"],
            "declared_license": row.get("declared_license"),
            "is_root": row.get("is_root"),
            "multimodal": row.get("multimodal"),
        }
        for row in props
    ]
    return {"nodes": nodes, "edges": edges}


@router.get("/api/models/{owner}/{name}/descendants")
def model_descendants(
    owner: str,
    name: str,
    depth: int = Query(2, ge=1, le=6),
    limit: int = Query(200, ge=1, le=500),
) -> dict[str, object]:
    model_id = _model_id(owner, name)
    rows = as_rows(ro_query("hub", D1, {"model_id": model_id}))
    if not rows:
        exists = as_rows(
            ro_query("hub", "MATCH (m:Model {id: $id}) RETURN m.id AS id", {"id": model_id})
        )
        if not exists:
            raise ApiError("MODEL_NOT_FOUND", f"No model '{model_id}' in the hub.")
    capped = rows[:limit]
    leverage = as_rows(ro_query("hub", D2, {"model_id": model_id}))
    fix = leverage[0] if leverage else {"descendants": 0, "not_inherited": 0}
    descendants = [
        {
            "id": row.get("id"),
            "declared_license": row.get("declared_license"),
        }
        for row in capped
    ]
    return {
        "descendants": descendants,
        "fix_leverage": {
            "descendants": int(fix.get("descendants") or 0),
            "not_inherited": int(fix.get("not_inherited") or 0),
        },
    }
