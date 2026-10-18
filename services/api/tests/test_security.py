"""G110: admin routes never answer without the admin token; tokens are compared in constant time."""

from __future__ import annotations

import inspect

from fastapi.testclient import TestClient

from app.main import app
from app.tenants import auth


def test_every_admin_route_refuses_without_the_token() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    paths = app.openapi()["paths"]
    admin = {path: methods for path, methods in paths.items() if path.startswith("/api/admin")}
    assert len(admin) >= 10
    for path, methods in admin.items():
        for method in methods:
            response = client.request(
                method.upper(),
                path,
                json={"model_id": "a/b", "reason": "probe", "model_ids": []},
                headers={"Authorization": "Bearer not-the-token"},
            )
            assert response.status_code in (401, 422), (method, path, response.status_code)


def test_token_checks_use_constant_time_compare() -> None:
    assert "compare_digest" in inspect.getsource(auth._const_eq)
