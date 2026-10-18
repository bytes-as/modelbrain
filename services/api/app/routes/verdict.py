"""POST /api/verdict. FalkorDB decides; this route only validates and ingests."""

from __future__ import annotations

import re

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.engine.verdict import verdict_from_graph
from app.errors import ApiError
from app.graph.db import ro_query
from app.graph.rows import as_rows
from app.jobs.runner import start_ingest

router = APIRouter()

MODEL_ID = re.compile(r"^[\w.-]+/[\w.-]+$")
ISO2 = re.compile(r"^[A-Z]{2}$")


class ContextIn(BaseModel):
    hq_country: str
    markets: list[str] | None = None
    commercial: bool = True
    mau: int = 0
    distributes_weights: bool = False
    end_user_only: bool = False


class VerdictIn(BaseModel):
    model_id: str
    context: ContextIn
    strict: bool = False


def _validate(body: VerdictIn) -> dict[str, object]:
    if not MODEL_ID.match(body.model_id):
        raise ApiError(
            "INVALID_INPUT",
            "Model id must look like owner/name.",
            hint="Example: meta-llama/Llama-3.2-1B.",
        )
    country = body.context.hq_country.strip().upper()
    if not ISO2.match(country):
        raise ApiError("INVALID_INPUT", "hq_country must be an ISO-2 code.", hint="Example: DE.")
    markets = [item.strip().upper() for item in (body.context.markets or [country])]
    if any(not ISO2.match(item) for item in markets):
        raise ApiError("INVALID_INPUT", "markets must be ISO-2 codes.")
    if body.context.mau < 0:
        raise ApiError("INVALID_INPUT", "mau must be zero or greater.")
    return {
        "hq_country": country,
        "markets": markets,
        "commercial": body.context.commercial,
        "mau": body.context.mau,
        "distributes_weights": body.context.distributes_weights,
        "end_user_only": body.context.end_user_only,
    }


def _needs_ingest(model_id: str) -> bool:
    rows = as_rows(
        ro_query(
            "hub",
            "MATCH (m:Model {id: $id}) RETURN m.ingested_at AS ingested_at",
            {"id": model_id},
        )
    )
    return not rows or rows[0].get("ingested_at") is None


@router.post("/api/verdict")
async def post_verdict(body: VerdictIn) -> dict[str, object]:
    context = _validate(body)
    try:
        if _needs_ingest(body.model_id):
            queued, job_id = await start_ingest(body.model_id, wait_s=4.0)
            if queued is not None:
                return JSONResponse(
                    status_code=202,
                    content={
                        "status": "QUEUED",
                        "job_id": job_id,
                        "events_url": f"/api/jobs/{job_id}/events",
                    },
                )
        return verdict_from_graph(
            body.model_id,
            context,
            graph="hub",
            min_tier=2 if body.strict else 1,
        )
    except ApiError:
        raise
    except Exception as exc:
        message = str(exc).lower()
        if "falkor" in message or "redis" in message or "connection" in message:
            raise ApiError(
                "GRAPH_UNAVAILABLE",
                "FalkorDB is not reachable.",
                hint="Start FalkorDB and retry.",
                retry_after_s=5,
            ) from exc
        raise
