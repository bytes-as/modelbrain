"""G065: sandbox create, write with token, fixed tenants reject writes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.errors import ApiError
from app.main import app
from app.tenants.auth import resolve_tenant


@pytest.fixture(autouse=True, scope="module")
def _demo_tenants() -> None:
    """Sandboxes copy a fictional tenant; seed them on an empty FalkorDB (as in CI)."""
    from app.graph import db
    from app.tenants.bootstrap import ensure_tenants

    db.connect(tries=5, delay_s=0.5)
    ensure_tenants()


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


def test_sandbox_survives_a_restart_and_orphans_are_removed() -> None:
    from app.graph import db
    from app.tenants import auth
    from app.tenants.sandbox import (
        cleanup_expired,
        create_sandbox,
        delete_sandbox,
        restore_registry,
    )

    db.connect(tries=5, delay_s=0.5)
    made = create_sandbox("kestrel")
    name, token = str(made["tenant"]), str(made["token"])
    orphan = "sbx_orphan" + name[-4:]
    db.copy_graph("tenant_kestrel", orphan)
    try:
        auth.drop_sandbox(name)  # simulate an API restart: in-memory registry is gone
        assert restore_registry() >= 1
        assert auth.resolve_tenant(name, token=token, write=True) == name
        cleanup_expired()
        graphs = db.list_graphs()
        assert orphan not in graphs
        assert name in graphs
    finally:
        delete_sandbox(name)
        if orphan in db.list_graphs():
            db.delete_graph(orphan)


def test_tenant_list_shows_only_the_callers_sandbox() -> None:
    client = TestClient(app)
    mine = client.post("/api/sandbox", json={"template": "kestrel"}).json()
    other = client.post("/api/sandbox", json={"template": "harbor"}).json()

    anonymous = {t["name"] for t in client.get("/api/tenants").json()}
    assert "tenant_kestrel" in anonymous
    assert mine["tenant"] not in anonymous and other["tenant"] not in anonymous

    listed = client.get("/api/tenants", headers={"X-Tenant-Token": mine["token"]}).json()
    names = {t["name"] for t in listed}
    assert mine["tenant"] in names
    assert other["tenant"] not in names


def test_registry_entry_without_a_graph_is_dropped() -> None:
    import time

    from app.tenants import auth
    from app.tenants.sandbox import cleanup_expired

    ghost = "sbx_0000ghost"
    auth.restore_sandbox(
        ghost, "hash", template="kestrel", expires_at=int(time.time() * 1000) + 3_600_000
    )
    cleanup_expired()
    assert ghost not in auth.list_sandbox_registry()
