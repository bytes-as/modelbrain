"""G105: per-IP rate limits return 429 with retry_after_s."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ratelimit import RateLimitMiddleware


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _app(clock: Clock) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, clock=clock)

    @app.post("/api/verdict")
    def verdict() -> dict:
        return {"ok": True}

    @app.post("/api/sandbox")
    def sandbox() -> dict:
        return {"ok": True}

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    return app


def _client(app: FastAPI, ip: str) -> TestClient:
    return TestClient(app, headers={"x-forwarded-for": ip})


def test_verdict_limit_and_retry_after() -> None:
    clock = Clock()
    client = _client(_app(clock), "203.0.113.7")
    codes = [client.post("/api/verdict").status_code for _ in range(31)]
    assert codes[:30] == [200] * 30 and codes[30] == 429
    body = client.post("/api/verdict").json()["error"]
    assert body["code"] == "RATE_LIMITED" and 1 <= body["retry_after_s"] <= 60
    clock.now += 61
    assert client.post("/api/verdict").status_code == 200


def test_limits_are_per_ip_and_health_is_exempt() -> None:
    clock = Clock()
    app = _app(clock)
    first, second = _client(app, "198.51.100.1"), _client(app, "198.51.100.2")
    assert [first.post("/api/sandbox").status_code for _ in range(4)] == [200, 200, 200, 429]
    assert second.post("/api/sandbox").status_code == 200
    assert all(first.get("/api/health").status_code == 200 for _ in range(200))


def test_admin_token_is_exempt() -> None:
    from app.config import get_settings

    clock = Clock()
    client = TestClient(
        _app(clock),
        headers={
            "x-forwarded-for": "192.0.2.9",
            "authorization": f"Bearer {get_settings().admin_token}",
        },
    )
    assert all(client.post("/api/sandbox").status_code == 200 for _ in range(10))
