"""G029: Hub unavailable returns HUB_UNAVAILABLE when nothing is cached."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.errors import ApiError
from app.main import app


@pytest.mark.asyncio
async def test_verdict_503_when_hub_unavailable() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.routes.verdict._needs_ingest", return_value=True):
            with patch(
                "app.routes.verdict.start_ingest",
                side_effect=ApiError(
                    "HUB_UNAVAILABLE",
                    "The Hugging Face Hub is unavailable and this model is not cached.",
                    hint="Try again shortly.",
                    retry_after_s=45,
                ),
            ):
                response = await client.post(
                    "/api/verdict",
                    json={
                        "model_id": "org/missing-model",
                        "context": {"hq_country": "DE"},
                    },
                )
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "HUB_UNAVAILABLE"
    assert body["error"]["retry_after_s"] == 45
