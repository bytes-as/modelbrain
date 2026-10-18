"""Hosted path endpoints (FLOWS F16, G128-G131)."""

from __future__ import annotations

import re

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel

from app.engine import hosted
from app.engine.verdict import verdict_from_graph
from app.errors import ApiError
from app.graph.db import ro_query
from app.graph.queries import O5
from app.graph.rows import as_rows
from app.routes.verdict import ContextIn, VerdictIn, _needs_ingest, _validate
from app.tenants.auth import require_admin

router = APIRouter()
MODEL_ID = re.compile(r"^[\w.-]+/[\w.-]+$")


class HostedVerdictIn(BaseModel):
    or_id: str
    context: ContextIn
    data_residency: str | list[str] | None = None
    strict: bool = False


@router.post("/api/admin/hosted/sync")
async def sync(authorization: str | None = Header(default=None)) -> dict:
    require_admin(authorization)
    return await hosted.sync_catalog()


@router.get("/api/hosted/providers/{owner}/{name}")
async def providers(owner: str, name: str, residency: str | None = Query(default=None)) -> dict:
    model_id = f"{owner}/{name}"
    if not MODEL_ID.match(model_id):
        raise ApiError("INVALID_INPUT", "Model id must look like owner/name.")
    return await hosted.where_can_i_run(model_id, residency)


@router.post("/api/hosted/verdict")
async def hosted_verdict(body: HostedVerdictIn) -> dict:
    if not MODEL_ID.match(body.or_id):
        raise ApiError("INVALID_INPUT", "or_id must look like vendor/model.")
    context = _validate(VerdictIn(model_id="a/b", context=body.context))
    context["distributes_weights"] = False
    rows = as_rows(ro_query("hub", O5, {"or_id": body.or_id}))
    if not rows:
        raise ApiError(
            "MODEL_NOT_FOUND",
            f"No hosted model '{body.or_id}' with Hugging Face weights in the catalogue.",
            hint="POST /api/admin/hosted/sync, or check the OpenRouter id.",
        )
    hf_id = str(rows[0]["hf_id"])
    if _needs_ingest(hf_id):
        from app.jobs.runner import _ingest_once

        await _ingest_once(hf_id)
    decided = verdict_from_graph(hf_id, context, graph="hub", min_tier=2 if body.strict else 1)
    decided = hosted.hosted_adjust(decided, bool(context.get("end_user_only")))
    decided["hosted"] = await hosted.where_can_i_run(hf_id, body.data_residency)
    decided["hosted"]["or_id"] = body.or_id
    return decided
