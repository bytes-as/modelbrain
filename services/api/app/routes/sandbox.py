"""POST /api/sandbox and task/ruling helpers for sandboxes."""

from __future__ import annotations

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel

from app.tenants import sandbox as sandbox_mod
from app.tenants.auth import list_sandbox_registry, resolve_tenant, token_hash
from app.tenants.bootstrap import list_tenants, overview
from app.tenants.conversations import list_conversations
from app.tenants.rulings import decision_trace
from app.tenants.tasks import approve_task, claim_task, list_tasks, reject_task

router = APIRouter()


class SandboxIn(BaseModel):
    template: str = "kestrel"


class ClaimIn(BaseModel):
    agent: str | None = None
    person_id: str | None = None


class ApproveIn(BaseModel):
    person_id: str


class RejectIn(BaseModel):
    person_id: str
    reason: str = "rejected"


@router.post("/api/sandbox")
def post_sandbox(body: SandboxIn) -> dict[str, object]:
    return sandbox_mod.create_sandbox(body.template)


@router.get("/api/tenants")
def get_tenants(
    x_tenant_token: str | None = Header(default=None, alias="X-Tenant-Token"),
) -> list[dict[str, object]]:
    found = list_tenants()
    # Only the caller's own sandbox: other visitors' sandboxes are private and short-lived.
    mine = token_hash(x_tenant_token) if x_tenant_token else None
    for name, record in list_sandbox_registry().items():
        if mine is None or record.get("token_hash") != mine:
            continue
        found.append(
            {
                "name": name,
                "company": f"Sandbox ({record.get('template')})",
                "hq_country": None,
                "kind": "sandbox",
            }
        )
    return found


@router.get("/api/tenants/{tenant}/overview")
def get_overview(
    tenant: str,
    x_tenant_token: str | None = Header(default=None, alias="X-Tenant-Token"),
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    graph = resolve_tenant(tenant, token=x_tenant_token, authorization=authorization, write=False)
    return overview(graph)


@router.get("/api/tenants/{tenant}/rulings/{ruling_id}/trace")
def get_trace(
    tenant: str,
    ruling_id: str,
    x_tenant_token: str | None = Header(default=None, alias="X-Tenant-Token"),
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    graph = resolve_tenant(tenant, token=x_tenant_token, authorization=authorization, write=False)
    return decision_trace(graph, ruling_id)


@router.get("/api/tenants/{tenant}/tasks")
def get_tasks(
    tenant: str,
    state: str | None = None,
    x_tenant_token: str | None = Header(default=None, alias="X-Tenant-Token"),
    authorization: str | None = Header(default=None),
) -> list[dict[str, object]]:
    graph = resolve_tenant(tenant, token=x_tenant_token, authorization=authorization, write=False)
    return list_tasks(graph, state)


@router.post("/api/tasks/{task_id}/claim")
def post_claim(
    task_id: str,
    body: ClaimIn,
    tenant: str = Query(...),
    x_tenant_token: str | None = Header(default=None, alias="X-Tenant-Token"),
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    graph = resolve_tenant(tenant, token=x_tenant_token, authorization=authorization, write=True)
    agent = body.agent or body.person_id or "agent"
    return {"claimed": claim_task(graph, task_id, agent)}


@router.post("/api/tasks/{task_id}/approve")
def post_approve(
    task_id: str,
    body: ApproveIn,
    tenant: str = Query(...),
    x_tenant_token: str | None = Header(default=None, alias="X-Tenant-Token"),
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    graph = resolve_tenant(tenant, token=x_tenant_token, authorization=authorization, write=True)
    return approve_task(graph, task_id, body.person_id)


@router.post("/api/tasks/{task_id}/reject")
def post_reject(
    task_id: str,
    body: RejectIn,
    tenant: str = Query(...),
    x_tenant_token: str | None = Header(default=None, alias="X-Tenant-Token"),
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    graph = resolve_tenant(tenant, token=x_tenant_token, authorization=authorization, write=True)
    return reject_task(graph, task_id, body.person_id, body.reason)


@router.get("/api/tenants/{tenant}/conversations")
def get_conversations(
    tenant: str,
    x_tenant_token: str | None = Header(default=None, alias="X-Tenant-Token"),
    authorization: str | None = Header(default=None),
) -> list[dict[str, object]]:
    graph = resolve_tenant(tenant, token=x_tenant_token, authorization=authorization, write=False)
    return list_conversations(graph)


@router.get("/api/tenants/{tenant}/events")
def get_events(
    tenant: str,
    limit: int = 50,
    x_tenant_token: str | None = Header(default=None, alias="X-Tenant-Token"),
    authorization: str | None = Header(default=None),
) -> list[dict[str, object]]:
    from app.graph import db
    from app.graph.rows import as_rows

    graph = resolve_tenant(tenant, token=x_tenant_token, authorization=authorization, write=False)
    return as_rows(
        db.ro_query(
            graph,
            """
            MATCH (e:Event)
            OPTIONAL MATCH (e)-[:ON]->(r:Ruling)
            RETURN e.id AS id, e.kind AS kind, e.at AS at, e.reason AS reason, r.id AS ruling_id
            ORDER BY e.at DESC LIMIT $limit
            """,
            {"limit": limit},
        )
    )
