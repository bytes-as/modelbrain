"""G065: sandbox create, write with token, fixed tenants reject writes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.errors import ApiError
from app.main import app
from app.tenants.auth import resolve_tenant


def test_sandbox_create_and_fixed_tenant_readonly() -> None:
    client = TestClient(app)
    response = client.post("/api/sandbox", json={"template": "kestrel"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tenant"].startswith("sbx_")
    assert body["token"]
    tenant = body["tenant"]
    token = body["token"]

    overview = client.get(
        f"/api/tenants/{tenant}/overview",
        headers={"X-Tenant-Token": token},
    )
    assert overview.status_code == 200

    # Fixed tenants reject writes without admin
    try:
        resolve_tenant("tenant_kestrel", write=True)
        assert False, "expected READ_ONLY_TENANT"
    except ApiError as exc:
        assert exc.code == "READ_ONLY_TENANT"
