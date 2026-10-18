"""POST /api/ingest and job status + SSE (G025)."""

from __future__ import annotations

import json
import re

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.errors import ApiError
from app.jobs.registry import jobs
from app.jobs.runner import start_ingest

router = APIRouter()

MODEL_ID = re.compile(r"^[\w.-]+/[\w.-]+$")


class IngestIn(BaseModel):
    model_id: str
    children: bool = False


@router.post("/api/ingest")
async def post_ingest(body: IngestIn) -> JSONResponse:
    if not MODEL_ID.match(body.model_id):
        raise ApiError(
            "INVALID_INPUT",
            "Model id must look like owner/name.",
            hint="Example: meta-llama/Llama-3.2-1B.",
        )
    _queued, job_id = await start_ingest(body.model_id, children=body.children, wait_s=None)
    return JSONResponse(
        status_code=202,
        content={"job_id": job_id, "events_url": f"/api/jobs/{job_id}/events"},
    )


@router.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    record = jobs().get(job_id)
    if record is None:
        raise ApiError("MODEL_NOT_FOUND", f"No job '{job_id}'.", hint="Start a new ingest.")
    payload: dict[str, object] = {
        "status": record.status,
        "nodes": record.nodes,
        "model_id": record.model_id,
    }
    if record.error:
        payload["error"] = record.error
    return payload


async def _sse_stream(job_id: str):
    record = jobs().get(job_id)
    if record is None:
        yield f"data: {json.dumps({'type': 'error', 'message': 'unknown job'})}\n\n"
        return
    queue = record.subscribe()
    while True:
        event = await queue.get()
        if event is None:
            break
        yield f"data: {json.dumps(event)}\n\n"
        if event.get("type") in ("done", "error"):
            break


@router.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str) -> StreamingResponse:
    record = jobs().get(job_id)
    if record is None:
        raise ApiError("MODEL_NOT_FOUND", f"No job '{job_id}'.", hint="Start a new ingest.")
    return StreamingResponse(_sse_stream(job_id), media_type="text/event-stream")
