"""Weight DNA endpoints (ADDENDUM_WEIGHT_DNA section 9)."""

from __future__ import annotations

import asyncio
import re

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel, Field

from app.engine import dna
from app.errors import ApiError
from app.graph.db import ro_query
from app.graph.queries import W4, W5, W6, W8, W16
from app.graph.rows import as_rows
from app.tenants.auth import require_admin

router = APIRouter()
MODEL_ID = re.compile(r"^[\w.-]+/[\w.-]+$")
_crawl_task: asyncio.Task | None = None


def _model_id(owner: str, name: str) -> str:
    model_id = f"{owner}/{name}"
    if not MODEL_ID.match(model_id):
        raise ApiError("INVALID_INPUT", "Model id is not valid.", hint="Use owner/name.")
    return model_id


@router.get("/api/dna/hidden")
def hidden(limit: int = Query(default=50, ge=1, le=500)) -> list[dict[str, object]]:
    return as_rows(ro_query("hub", W4, {"limit": limit}))


@router.get("/api/dna/conflicts")
def conflicts(limit: int = Query(default=50, ge=1, le=500)) -> list[dict[str, object]]:
    rows = as_rows(ro_query("hub", W5, {"limit": 500}))
    return dna.verified_conflicts("hub", rows)[:limit]


@router.get("/api/dna/coverage")
def coverage() -> dict[str, object]:
    rows = as_rows(ro_query("hub", W6))
    counts = {str(r["status"]): int(r["models"]) for r in rows}
    return {"total": sum(counts.values()), "by_status": counts}


@router.get("/api/dna/exposure/{owner}/{name}")
def exposure(owner: str, name: str, strict: bool = False) -> list[dict[str, object]]:
    model_id = _model_id(owner, name)
    return as_rows(ro_query("hub", W8, {"id": model_id, "min_tier": 2 if strict else 1}))


class CrawlRequest(BaseModel):
    model_ids: list[str] = Field(default_factory=list, max_length=3000)
    include_scout_findings: bool = True
    include_gguf: int = Field(default=0, ge=0, le=300)
    force: bool = False


async def _ingest(model_id: str) -> None:
    from app.jobs.runner import _ingest_once

    await _ingest_once(model_id)


@router.post("/api/admin/dna/crawl")
async def start_crawl(body: CrawlRequest, authorization: str | None = Header(default=None)) -> dict:
    require_admin(authorization)
    global _crawl_task
    if _crawl_task is not None and not _crawl_task.done():
        raise ApiError(
            "JOB_RUNNING", "A crawl is already running.", hint="GET /api/admin/dna/crawl"
        )
    ids = [m for m in body.model_ids if MODEL_ID.match(m)]
    if body.include_scout_findings:
        ids += [m for m in dna.scout_findings_ids() if m not in ids]
    if body.include_gguf:
        ids += [m for m in await dna.popular_gguf_repos(body.include_gguf) if m not in ids]
    _crawl_task = asyncio.create_task(dna.crawl(ids, ingest=_ingest, force=body.force))
    return {"state": "started", "queued": len(ids)}


@router.get("/api/admin/dna/crawl")
def crawl_status(authorization: str | None = Header(default=None)) -> dict:
    require_admin(authorization)
    return dna.crawl_status()


@router.post("/api/admin/dna/resolve")
def resolve(authorization: str | None = Header(default=None)) -> dict:
    require_admin(authorization)
    report = dna.run_dna_resolver("hub")
    return {k: v for k, v in report.items() if k != "results"} | {"results": report["results"][:50]}


@router.get("/api/admin/dna/last")
def last(authorization: str | None = Header(default=None)) -> dict:
    require_admin(authorization)
    return dna.last_report()


@router.post("/api/admin/dna/reset-edges")
def reset_edges(authorization: str | None = Header(default=None)) -> dict:
    require_admin(authorization)
    return {"removed": dna.reset_weight_edges("hub")}


@router.get("/api/dna/inherits/{owner}/{name}")
def inherits(owner: str, name: str, strict: bool = False) -> dict[str, object]:
    """One FalkorDB query: weights -> nearest parent -> ancestry -> licences -> clauses."""
    import time

    from app.config import get_settings

    model_id = _model_id(owner, name)
    started = time.perf_counter()
    rows = as_rows(
        ro_query(
            "hub",
            W16,
            {
                "id": model_id,
                "k": 50,
                "min_sim": get_settings().dna_derived_min,
                "min_tier": 2 if strict else 1,
            },
        )
    )
    return {
        "model_id": model_id,
        "rows": rows,
        "ms": round((time.perf_counter() - started) * 1000, 1),
        "cypher": W16.strip(),
    }
