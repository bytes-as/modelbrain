"""Graph algorithm endpoints (A1-A4) and proof-path."""

from __future__ import annotations

import re

from fastapi import APIRouter, Query

from app.errors import ApiError
from app.graph.db import ro_query
from app.graph.queries import A1, A2, A3, A4
from app.graph.rows import as_rows

router = APIRouter()
MODEL_ID = re.compile(r"^[\w.-]+/[\w.-]+$")


@router.get("/api/algo/relabel-hubs")
def relabel_hubs() -> list[dict[str, object]]:
    return as_rows(ro_query("hub", A1))


@router.get("/api/algo/chokepoints")
def chokepoints() -> list[dict[str, object]]:
    return as_rows(ro_query("hub", A2))


@router.get("/api/algo/families")
def families() -> list[dict[str, object]]:
    return as_rows(ro_query("hub", A3))


@router.get("/api/algo/hidden-lineage")
def hidden_lineage() -> list[dict[str, object]]:
    from app.engine.resolver import last_report
    from app.graph.queries import R1

    try:
        rows = as_rows(ro_query("hub", R1))
    except Exception:
        rows = []
    edges = list(last_report().get("edges") or [])
    out = []
    for row in rows:
        model_ids = [str(m) for m in (row.get("model_ids") or []) if m]
        if len(model_ids) < 2:
            continue
        related = [e for e in edges if e.get("child") in model_ids or e.get("parent") in model_ids]
        out.append(
            {
                "component_id": row.get("componentId"),
                "model_ids": model_ids,
                "inferred_edges": related,
            }
        )
    return out


@router.get("/api/models/{owner}/{name}/proof-path")
def proof_path(owner: str, name: str, root_id: str = Query(...)) -> dict[str, object]:
    model_id = f"{owner}/{name}"
    if not MODEL_ID.match(model_id) or not MODEL_ID.match(root_id):
        raise ApiError("INVALID_INPUT", "Model ids must look like owner/name.")
    rows = as_rows(ro_query("hub", A4, {"model_id": model_id, "root_id": root_id}))
    if not rows:
        return {"no_path": True, "path": [], "hops": 0}
    row = rows[0]
    return {
        "no_path": bool(row.get("no_path")),
        "path": row.get("path") or [],
        "hops": int(row.get("hops") or 0),
    }
