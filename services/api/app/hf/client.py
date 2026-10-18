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


_last_failure_at = 0.0
DEGRADED_FOR_S = 300


def hub_status() -> str:
    """'ok' unless a Hub call failed (rate limit, 5xx, network) in the last five minutes."""
    return "degraded" if time.time() - _last_failure_at < DEGRADED_FOR_S else "ok"


class HubUnavailable(Exception):
    def __init__(self, message: str, *, retry_after_s: int = 30) -> None:
        global _last_failure_at
        super().__init__(message)
        self.retry_after_s = retry_after_s
        _last_failure_at = time.time()


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
                # Renamed repos answer 307 to the new name; follow it.
                response = await self._http.get(url, follow_redirects=True)
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

    async def get_range(self, url: str, start: int, end: int) -> HFResponse:
        """Fetch bytes [start, end] of a file, following the CDN redirect.

        URLs are pinned to a commit sha, so ranges are cached without expiry.
        """
        if end < start:
            raise ValueError("empty range")
        key = f"range:{url}:{start}-{end}"
        cached = self.cache.get(key, max_age_s=None)
        if cached is not None:
            return HFResponse(206, cached)

        last_error = "Hugging Face file request failed."
        for attempt in range(3):
            await self.limiter.acquire()
            want = end - start + 1
            try:
                async with self._http.stream(
                    "GET",
                    url,
                    headers={"Range": f"bytes={start}-{end}"},
                    follow_redirects=True,
                    timeout=30.0,
                ) as response:
                    status = response.status_code
                    retry_after = _retry_after(response, default=20)
                    body = b""
                    if status in (200, 206):
                        # Never read more than requested, even if the server
                        # ignores Range and starts sending the whole file.
                        async for chunk in response.aiter_bytes():
                            body += chunk
                            if len(body) >= want:
                                break
                        body = body[:want]
            except httpx.HTTPError as exc:
                last_error = f"Hugging Face file request failed: {type(exc).__name__}"
                if attempt >= 2:
                    break
                await self.sleep(float(2**attempt))
                continue
            if status == 429:
                if attempt >= 2:
                    raise HubUnavailable(
                        "Hugging Face Hub rate limited the request.", retry_after_s=retry_after
                    )
                await self.sleep(float(retry_after))
                continue
            if status >= 500:
                last_error = f"Hugging Face Hub returned {status}."
                if attempt >= 2:
                    break
                await self.sleep(float(2**attempt))
                continue
            if status == 200 and start != 0:
                # Range ignored: the bytes we read are from offset 0, not `start`.
                return HFResponse(416, b"")
            if status in (200, 206):
                self.cache.put(key, body)
                return HFResponse(206, body)
            return HFResponse(status, b"")
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
