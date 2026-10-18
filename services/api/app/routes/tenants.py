"""Fixed demo tenants. Visitors do not write these graphs."""

from fastapi import APIRouter

from app.errors import ApiError
from app.tenants.bootstrap import TENANTS, list_tenants, overview

router = APIRouter()


@router.get("/api/tenants")
def get_tenants() -> list[dict[str, object]]:
    return list_tenants()


@router.get("/api/tenants/{tenant}/overview")
def get_overview(tenant: str) -> dict[str, object]:
    if tenant not in TENANTS:
        raise ApiError(
            "MODEL_NOT_FOUND", f"No tenant '{tenant}'.", hint="Use tenant_kestrel or tenant_harbor."
        )
    return overview(tenant)
