"""ModelBrain API entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.errors import install_error_handlers
from app.graph.db import connect, health_snapshot
from app.observe import RequestIdMiddleware, configure_logging

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
    yield


app = FastAPI(title="ModelBrain", version=VERSION, lifespan=lifespan)
app.add_middleware(RequestIdMiddleware)
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
