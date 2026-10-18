"""G020: Hub client retries 429 and 5xx, and serves a fresh disk cache."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.hf.cache import DiskCache
from app.hf.client import HFClient, HubUnavailable


class Script:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = responses
        self.calls = 0

    def __call__(self, _request: httpx.Request) -> httpx.Response:
        item = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return item


@pytest.mark.asyncio
async def test_retries_429_then_caches(tmp_path: Path) -> None:
    script = Script(
        [
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    client = HFClient(
        token="hf_test",
        cache=DiskCache(tmp_path),
        transport=httpx.MockTransport(script),
        sleep=sleep,
    )
    try:
        first = await client.get("https://huggingface.co/api/models/org/name")
        second = await client.get("https://huggingface.co/api/models/org/name")
    finally:
        await client.aclose()
    assert json.loads(first.body) == {"ok": True}
    assert second.body == first.body
    assert script.calls == 2
    assert slept == [0.0]
    assert client.limiter.capacity == 400


@pytest.mark.asyncio
async def test_retries_5xx_with_backoff(tmp_path: Path) -> None:
    script = Script(
        [
            httpx.Response(503),
            httpx.Response(502),
            httpx.Response(200, content=b'{"n":1}'),
        ]
    )
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    client = HFClient(
        token="",
        cache=DiskCache(tmp_path),
        transport=httpx.MockTransport(script),
        sleep=sleep,
    )
    try:
        response = await client.get("https://huggingface.co/api/models/org/name")
    finally:
        await client.aclose()
    assert response.status == 200
    assert slept == [1.0, 2.0]
    assert client.limiter.capacity == 90


@pytest.mark.asyncio
async def test_gives_up_and_reports_hub_unavailable(tmp_path: Path) -> None:
    script = Script(
        [httpx.Response(500), httpx.Response(500), httpx.Response(500), httpx.Response(500)]
    )

    async def sleep(_seconds: float) -> None:
        return None

    client = HFClient(
        token="hf_test",
        cache=DiskCache(tmp_path),
        transport=httpx.MockTransport(script),
        sleep=sleep,
    )
    try:
        with pytest.raises(HubUnavailable):
            await client.get("https://huggingface.co/api/models/missing/repo")
    finally:
        await client.aclose()
    assert script.calls == 4


@pytest.mark.asyncio
async def test_stale_cache_when_hub_stays_down(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path)
    cache.put("https://huggingface.co/api/models/org/name", b'{"cached":true}')
    script = Script([httpx.Response(500)] * 4)

    async def sleep(_seconds: float) -> None:
        return None

    client = HFClient(
        token="hf_test", cache=cache, transport=httpx.MockTransport(script), sleep=sleep
    )
    try:
        response = await client.get("https://huggingface.co/api/models/org/name", ttl_s=0)
    finally:
        await client.aclose()
    assert response.stale is True
    assert json.loads(response.body) == {"cached": True}
