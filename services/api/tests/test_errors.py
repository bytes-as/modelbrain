"""G006: 404, 422 and 503 use the API error envelope."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.errors import ApiError, install_error_handlers
from app.main import app


def _client_with_probes() -> TestClient:
    probe = FastAPI()
    install_error_handlers(probe)

    class Body(BaseModel):
        hq_country: str

    @probe.post("/api/validate")
    def validate(_body: Body) -> dict[str, bool]:
        return {"ok": True}

    @probe.get("/api/graph-down")
    def graph_down() -> dict[str, bool]:
        raise ApiError(
            "GRAPH_UNAVAILABLE",
            "FalkorDB is not reachable.",
            hint="Start FalkorDB and retry.",
            retry_after_s=5,
        )

    return TestClient(probe, raise_server_exceptions=False)


def test_unknown_route_is_404_envelope() -> None:
    response = TestClient(app, raise_server_exceptions=False).get("/api/does-not-exist")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "MODEL_NOT_FOUND"
    assert error["message"]
    assert error["hint"]
    assert error["retry_after_s"] is None
    assert response.headers["x-request-id"]


def test_validation_is_422_envelope() -> None:
    response = _client_with_probes().post("/api/validate", json={})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error == {
        "code": "INVALID_INPUT",
        "message": "Request failed validation.",
        "hint": "Check: hq_country.",
        "retry_after_s": None,
    }


def test_graph_unavailable_is_503_envelope() -> None:
    response = _client_with_probes().get("/api/graph-down")
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "GRAPH_UNAVAILABLE"
    assert error["message"] == "FalkorDB is not reachable."
    assert error["hint"] == "Start FalkorDB and retry."
    assert error["retry_after_s"] == 5
