"""ModelBrain API entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import install_error_handlers
from app.graph.db import connect, health_snapshot
from app.graph.schema import apply_schema
from app.observe import OriginAllowlistMiddleware, RequestIdMiddleware, configure_logging

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


@app.get("/api/health")
def health() -> dict[str, object]:
    snap = health_snapshot()
    up = snap["falkordb"] == "up"
    return {
        "ok": up,
        "falkordb": snap["falkordb"],
        "graphs": snap["graphs"],
        "hub_models": snap["hub_models"],
        "clauses": {"resolved": 0, "unresolved": 0},
        "hf": "degraded",
        "version": VERSION,
    }
