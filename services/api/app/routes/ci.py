"""POST /api/ci/check: verdicts for every model a pull request loads (G091, FLOWS F12)."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.engine.verdict import verdict_from_graph
from app.errors import ApiError
from app.jobs.runner import _ingest_once
from app.routes.verdict import MODEL_ID, ContextIn, VerdictIn, _needs_ingest, _validate

router = APIRouter()
log = logging.getLogger("modelbrain.ci")
INGEST_TIMEOUT_S = 45.0


class CiIn(BaseModel):
    model_ids: list[str] = Field(min_length=1, max_length=20)
    context: ContextIn
    strict: bool = False


@router.post("/api/ci/check")
async def ci_check(body: CiIn) -> dict[str, object]:
    context = _validate(VerdictIn(model_id="a/b", context=body.context))
    results: list[dict[str, object]] = []
    for model_id in dict.fromkeys(body.model_ids):
        if not MODEL_ID.match(model_id):
            results.append({"model_id": model_id, "verdict": "INVALID_ID"})
            continue
        try:
            if _needs_ingest(model_id):
                await asyncio.wait_for(_ingest_once(model_id), timeout=INGEST_TIMEOUT_S)
            decided = verdict_from_graph(
                model_id, context, graph="hub", min_tier=2 if body.strict else 1
            )
        except (TimeoutError, ApiError) as exc:
            log.warning("ci check could not decide", extra={"model_id": model_id})
            results.append(
                {"model_id": model_id, "verdict": "UNAVAILABLE", "reason": str(exc) or "timeout"}
            )
            continue
        paths = decided.get("paths") or []
        deepest = max(paths, key=lambda p: len(p["path"]))["path"] if paths else [model_id]
        results.append(
            {
                "model_id": model_id,
                "verdict": decided["verdict"],
                "declared_license": decided.get("declared_license"),
                "path": deepest,
                "blocking": [hit["clause_id"] for hit in decided.get("blocking") or []],
                "obligations": [hit["clause_id"] for hit in decided.get("obligations") or []],
            }
        )
    failing = {"BLOCKED"} | ({"CANNOT_DETERMINE"} if body.strict else set())
    return {
        "fail": any(r["verdict"] in failing for r in results),
        "results": results,
        "disclaimer": "Automated screening, not legal advice.",
    }
