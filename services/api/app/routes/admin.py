"""Admin endpoints: resolver report and declared_differs batch."""

from __future__ import annotations

from fastapi import APIRouter, Header

from app.engine.resolver import last_report, run_resolver, set_declared_differs
from app.tenants.auth import require_admin

router = APIRouter()


@router.get("/api/admin/resolver/last")
def resolver_last(authorization: str | None = Header(default=None)) -> dict:
    require_admin(authorization)
    return last_report()


@router.post("/api/admin/resolver/run")
def resolver_run(authorization: str | None = Header(default=None)) -> dict:
    require_admin(authorization)
    return run_resolver("hub")


@router.post("/api/admin/declared-differs")
def declared_differs(authorization: str | None = Header(default=None)) -> dict:
    require_admin(authorization)
    return {"updated": set_declared_differs("hub")}
