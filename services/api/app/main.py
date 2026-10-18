"""ModelBrain API entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import install_error_handlers
from app.graph.db import connect, health_snapshot, ro_query
from app.graph.queries import C4
from app.graph.rows import as_rows
from app.graph.schema import apply_schema
from app.observe import OriginAllowlistMiddleware, RequestIdMiddleware, configure_logging
from app.routes.tenants import router as tenants_router
from app.routes.verdict import router as verdict_router
from app.tenants.bootstrap import ensure_tenants

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
app.include_router(tenants_router)


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
