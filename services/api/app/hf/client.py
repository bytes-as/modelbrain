"""Async Hugging Face client: shared limiter, cache, timeout, retries."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx

from app.hf.cache import DiskCache

Sleep = Callable[[float], Awaitable[None]]

JSON_TTL_S = 6 * 60 * 60
WINDOW_S = 5 * 60


class HubUnavailable(Exception):
    def __init__(self, message: str, *, retry_after_s: int = 30) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


class SlidingLimiter:
    def __init__(self, capacity: int, window_s: float = WINDOW_S) -> None:
        self.capacity = capacity
        self.window_s = window_s
        self._hits: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                while self._hits and now - self._hits[0] >= self.window_s:
                    self._hits.popleft()
                if len(self._hits) < self.capacity:
                    self._hits.append(now)
                    return
                wait = self.window_s - (now - self._hits[0])
            await asyncio.sleep(max(wait, 0.01))


class HFResponse:
    def __init__(self, status: int, body: bytes, *, stale: bool = False) -> None:
        self.status = status
        self.body = body
        self.stale = stale

    def json(self) -> object:
        import json

        return json.loads(self.body)


class HFClient:
    """One process-wide client. Tests pass their own instance."""

    def __init__(
        self,
        *,
        token: str = "",
        cache: DiskCache | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
        timeout_s: float = 10.0,
    ) -> None:
        self.token = token
        self.cache = cache or DiskCache(Path("/tmp/modelbrain-hf"))
        self.sleep = sleep
        self.limiter = SlidingLimiter(400 if token else 90)
        headers = {"User-Agent": "modelbrain"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._http = httpx.AsyncClient(transport=transport, timeout=timeout_s, headers=headers)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def get(
        self,
        url: str,
        *,
        cache_key: str | None = None,
        ttl_s: float | None = JSON_TTL_S,
    ) -> HFResponse:
        key = cache_key or url
        cached = self.cache.get(key, max_age_s=ttl_s)
        if cached is not None:
            return HFResponse(200, cached, stale=False)

        last_error = "Hugging Face Hub is unavailable."
        for attempt in range(4):
            await self.limiter.acquire()
            try:
                response = await self._http.get(url)
            except httpx.HTTPError as exc:
                last_error = f"Hugging Face Hub request failed: {type(exc).__name__}"
                if attempt >= 3:
                    break
                await self.sleep(float(2**attempt))
                continue

            if response.status_code == 429:
                retry_after = _retry_after(response, default=20)
                last_error = "Hugging Face Hub rate limited the request."
                if attempt >= 3:
                    raise HubUnavailable(last_error, retry_after_s=retry_after)
                await self.sleep(float(retry_after))
                continue

            if response.status_code >= 500:
                last_error = f"Hugging Face Hub returned {response.status_code}."
                if attempt >= 3:
                    break
                await self.sleep(float(2**attempt))
                continue

            body = response.content
            if response.status_code == 200:
                self.cache.put(key, body)
            return HFResponse(response.status_code, body)

        stale = self.cache.get(key, max_age_s=None)
        if stale is not None:
            return HFResponse(200, stale, stale=True)
        raise HubUnavailable(last_error)

    async def get_json(self, url: str) -> object:
        response = await self.get(url)
        if response.status >= 400:
            return {"_status": response.status}
        return response.json()


def _retry_after(response: httpx.Response, default: int) -> int:
    raw = response.headers.get("Retry-After", "")
    try:
        return max(int(float(raw)), 0)
    except ValueError:
        return default
