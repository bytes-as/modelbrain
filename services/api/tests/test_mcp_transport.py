"""Deployed /mcp: the public API host is allowed (no 421) and links point at the web app."""

import pytest
from fastapi.testclient import TestClient
from mcp.server.fastmcp import FastMCP

from app import mcp_server
from app.config import load_settings

TOOLS_LIST = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
HEADERS = {"accept": "application/json, text/event-stream", "content-type": "application/json"}


@pytest.fixture
def deployed(monkeypatch):
    settings = load_settings(
        {
            "ADMIN_TOKEN": "admin-secret",
            "PUBLISHER_SALT": "salt-secret",
            "NEXT_PUBLIC_API_URL": "https://api.example.app",
            "CORS_ORIGINS": "https://web.example.app",
        }
    )
    monkeypatch.setattr(mcp_server, "get_settings", lambda: settings)


def _probe() -> TestClient:
    server = FastMCP(
        "probe", stateless_http=True, transport_security=mcp_server.transport_security()
    )

    @server.tool()
    def ping() -> str:
        return "pong"

    return server.streamable_http_app()


@pytest.mark.parametrize(
    ("base_url", "status"),
    [
        ("https://api.example.app", 200),
        ("http://localhost:8000", 200),
        ("https://evil.example", 421),
    ],
)
def test_host_allowlist(deployed, base_url: str, status: int) -> None:
    with TestClient(_probe(), base_url=base_url) as client:
        response = client.post("/mcp", json=TOOLS_LIST, headers=HEADERS)
    assert response.status_code == status


def test_foreign_origin_rejected(deployed) -> None:
    with TestClient(_probe(), base_url="https://api.example.app") as client:
        response = client.post(
            "/mcp", json=TOOLS_LIST, headers={**HEADERS, "origin": "https://evil.example"}
        )
    assert response.status_code == 403


def test_details_link_points_at_web_app(deployed) -> None:
    text = mcp_server._format_can_i_use(
        {"verdict": "ALLOWED", "model_id": "acme/model", "paths": []}, "US"
    )
    assert "Details: https://web.example.app/m/acme/model?hq=US" in text
