"""Fan-out, Xkev replay and compounding endpoints (FLOWS F8, F9, F11)."""

from __future__ import annotations

import re

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel, Field

from app.engine import watcher
from app.errors import ApiError
from app.graph.db import ro_query
from app.graph.queries import X15
from app.graph.rows import as_rows
from app.tenants.auth import require_admin, resolve_tenant

router = APIRouter()
MODEL_ID = re.compile(r"^[\w.-]+/[\w.-]+$")


def _check_model(model_id: str) -> str:
    if not MODEL_ID.match(model_id):
        raise ApiError("INVALID_INPUT", "Model id is not valid.", hint="Use owner/name.")
    return model_id


class FanOutIn(BaseModel):
    model_id: str
    reason: str = Field(min_length=3, max_length=300)


class ConfirmIn(BaseModel):
    child: str
    parent: str
    person_id: str = Field(min_length=1, max_length=80)


class ReplayRunIn(BaseModel):
    tenant: str


@router.get("/api/replay/xkev")
def replay_view() -> dict:
    return watcher.replay_view()


@router.post("/api/replay/xkev/run")
def replay_run(
    body: ReplayRunIn,
    x_tenant_token: str | None = Header(default=None, alias="X-Tenant-Token"),
    authorization: str | None = Header(default=None),
) -> dict:
    graph = resolve_tenant(
        body.tenant, token=x_tenant_token, authorization=authorization, write=True
    )
    return watcher.run_replay(graph)


@router.post("/api/admin/fan-out")
def admin_fan_out(body: FanOutIn, authorization: str | None = Header(default=None)) -> dict:
    require_admin(authorization)
    return watcher.fan_out(_check_model(body.model_id), body.reason)


@router.get("/api/fanouts")
def fan_outs(limit: int = Query(default=20, ge=1, le=100)) -> list[dict[str, object]]:
    return watcher.recent_fan_outs(limit)


@router.get("/api/models/{owner}/{name}/fix-leverage")
def fix_leverage(owner: str, name: str) -> dict:
    model_id = _check_model(f"{owner}/{name}")
    return {"model_id": model_id, **watcher.leverage(model_id)}


@router.post("/api/tenants/{tenant}/confirm")
def confirm(
    tenant: str,
    body: ConfirmIn,
    x_tenant_token: str | None = Header(default=None, alias="X-Tenant-Token"),
    authorization: str | None = Header(default=None),
) -> dict:
    graph = resolve_tenant(tenant, token=x_tenant_token, authorization=authorization, write=True)
    return watcher.confirm_edge(
        graph,
        _check_model(body.child),
        _check_model(body.parent),
        body.person_id,
        include_fixed=not graph.startswith("sbx_"),
    )


@router.post("/api/admin/demo/compounding")
def reset_compounding(authorization: str | None = Header(default=None)) -> dict:
    require_admin(authorization)
    return watcher.reset_compounding_demo()


@router.get("/api/demo/compounding")
def compounding_state() -> dict:
    child, parent = watcher.DEMO_EDGE
    state = watcher.edge_state(child, parent)
    return {"child": child, "parent": parent, "edge": state}


class CheckIn(BaseModel):
    model_id: str
    tenant: str | None = None


async def _fresh_ingest(model_id: str) -> None:
    """Re-ingest straight from the Hub, bypassing the response cache."""
    import tempfile
    from pathlib import Path

    from app.agents.scout import ingest
    from app.config import get_settings
    from app.hf.cache import DiskCache
    from app.hf.client import HFClient
    from app.hf.live import LiveHub
    from app.jobs.runner import _hub_resources

    table, roots = _hub_resources()
    with tempfile.TemporaryDirectory() as tmp:
        client = HFClient(token=get_settings().hf_token, cache=DiskCache(Path(tmp)))
        try:
            await ingest(model_id, LiveHub(client), table=table, roots=roots, graph="hub")
        finally:
            await client.aclose()


@router.post("/api/watch/check")
async def watch_check(
    body: CheckIn,
    x_tenant_token: str | None = Header(default=None, alias="X-Tenant-Token"),
    authorization: str | None = Header(default=None),
) -> dict:
    model_id = _check_model(body.model_id)
    graphs: list[str] | None = None
    if body.tenant:
        graph = resolve_tenant(
            body.tenant, token=x_tenant_token, authorization=authorization, write=True
        )
        rows = as_rows(ro_query(graph, X15, {"id": model_id}))
        if not rows or int(rows[0]["deployments"]) == 0:
            raise ApiError(
                "NOT_ALLOWLISTED",
                "Sandbox users can only check models their company deploys.",
                hint="Pick a model from your deployments.",
            )
        graphs = [graph]
    else:
        require_admin(authorization)
    return await watcher.check_now(model_id, _fresh_ingest, graphs=graphs)


@router.get("/api/admin/watch/last")
def watch_last(authorization: str | None = Header(default=None)) -> dict:
    require_admin(authorization)
    return watcher.watch_last()


@router.post("/api/admin/watch/run")
async def watch_run(authorization: str | None = Header(default=None)) -> dict:
    require_admin(authorization)
    return await watcher.watch_once(_fresh_ingest)


@router.post("/api/admin/discussions/run")
async def discussions_run(authorization: str | None = Header(default=None)) -> dict:
    require_admin(authorization)
    return await watcher.refresh_discussions()


@router.get("/api/models/{owner}/{name}/discussions")
def model_discussions(owner: str, name: str) -> list[dict[str, object]]:
    from app.engine.discussions import discussions_for

    return discussions_for(_check_model(f"{owner}/{name}"))


@router.post("/api/admin/licence-watch/run")
async def licence_watch_run(authorization: str | None = Header(default=None)) -> dict:
    require_admin(authorization)
    from app.engine import licence_watch

    return await licence_watch.run_watch()


@router.get("/api/admin/licence-watch/last")
def licence_watch_last(authorization: str | None = Header(default=None)) -> dict:
    require_admin(authorization)
    from app.engine import licence_watch

    return licence_watch.last_report()


@router.post("/api/admin/licences/resolve-custom")
async def resolve_custom(authorization: str | None = Header(default=None)) -> dict:
    require_admin(authorization)
    from pathlib import Path

    from app.config import get_settings
    from app.engine import licence_watch
    from app.hf.cache import DiskCache
    from app.hf.client import HFClient

    client = HFClient(token=get_settings().hf_token, cache=DiskCache(Path("/tmp/modelbrain-hf")))
    try:
        return await licence_watch.resolve_custom_licences(client)
    finally:
        await client.aclose()
