"""Fan-out, Xkev replay and compounding endpoints (FLOWS F8, F9, F11)."""

from __future__ import annotations

import re

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel, Field

from app.engine import watcher
from app.errors import ApiError
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
        graph, _check_model(body.child), _check_model(body.parent), body.person_id
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
