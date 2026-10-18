"""ModelBrain API entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.errors import install_error_handlers
from app.graph.db import connect, health_snapshot, ro_query
from app.graph.queries import C4
from app.graph.rows import as_rows
from app.graph.schema import apply_schema
from app.jobs.runner import schedule_prewarm
from app.mcp_server import mcp, mcp_http_app
from app.observe import OriginAllowlistMiddleware, RequestIdMiddleware, configure_logging
from app.routes.admin import router as admin_router
from app.routes.algo import router as algo_router
from app.routes.dna import router as dna_router
from app.routes.eval import router as eval_router
from app.routes.ingest import router as ingest_router
from app.routes.loop import router as loop_router
from app.routes.models import router as models_router
from app.routes.sandbox import router as tenants_router
from app.routes.verdict import router as verdict_router
from app.tenants.bootstrap import ensure_tenants
from app.tenants.sandbox import cleanup_expired

configure_logging()
log = logging.getLogger("modelbrain")

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_settings()
    try:
        connect()
    except Exception:
        log.warning("starting with falkordb down")
    else:
        apply_schema()
        try:
            ensure_tenants()
        except Exception:
            log.exception("tenant bootstrap failed")
        try:
            from app.engine.dna import ensure_index, mark_references

            ensure_index("hub")
            mark_references("hub")
        except Exception:
            log.exception("weight dna bootstrap failed")
        try:
            cleanup_expired()
        except Exception:
            log.warning("sandbox cleanup failed")
        schedule_prewarm()
    # MCP session manager (required for streamable HTTP)
    mcp.streamable_http_app()
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="ModelBrain", version=VERSION, lifespan=lifespan)
_origins = get_settings().cors_origins
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.add_middleware(OriginAllowlistMiddleware, origins=_origins)
install_error_handlers(app)
app.include_router(verdict_router)
app.include_router(ingest_router)
app.include_router(models_router)
app.include_router(algo_router)
app.include_router(admin_router)
app.include_router(eval_router)
app.include_router(tenants_router)
app.include_router(dna_router)
app.include_router(loop_router)


@app.get("/api/health")
def health() -> dict[str, object]:
    snap = health_snapshot()
    up = snap["falkordb"] == "up"
    clauses = {"resolved": 0, "unresolved": 0}
    if up:
        try:
            found = as_rows(ro_query("hub", C4))
            if found:
                clauses = {
                    "resolved": int(found[0].get("resolved") or 0),
                    "unresolved": int(found[0].get("unresolved") or 0),
                }
        except Exception:
            log.warning("clause counts unavailable")
    return {
        "ok": up,
        "falkordb": snap["falkordb"],
        "graphs": snap["graphs"],
        "hub_models": snap["hub_models"],
        "clauses": clauses,
        "hf": "degraded",
        "version": VERSION,
    }


@app.api_route(
    "/api/{rest:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
def api_not_found(rest: str) -> None:
    # Unknown /api paths get the JSON envelope instead of falling through
    # to the MCP mount below, which answers with plain text.
    raise StarletteHTTPException(status_code=404)


# Mount MCP last. FastMCP's app already serves `/mcp`
# (BLUEPRINT: mount at "/", not under another /mcp prefix).
app.mount("/", mcp_http_app())
