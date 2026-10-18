"""G044: FalkorDB down returns GRAPH_UNAVAILABLE."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def test_verdict_503_when_falkordb_is_down() -> None:
    client = TestClient(app)
    with patch("app.routes.verdict._needs_ingest", return_value=False):
        with patch(
            "app.routes.verdict.verdict_from_graph",
            side_effect=ConnectionError("Error connecting to Redis"),
        ):
            response = client.post(
                "/api/verdict",
                json={
                    "model_id": "OPEA/Llama-3.2V-11B-cot-int4-sym-inc",
                    "context": {"hq_country": "DE"},
                },
            )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "GRAPH_UNAVAILABLE"


def test_any_route_returns_503_when_falkordb_is_down() -> None:
    import redis.exceptions

    client = TestClient(app, raise_server_exceptions=False)
    with patch(
        "app.routes.dna.ro_query",
        side_effect=redis.exceptions.ConnectionError("Error 111 connecting to falkordb:6379"),
    ):
        response = client.get("/api/dna/hidden")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "GRAPH_UNAVAILABLE"
