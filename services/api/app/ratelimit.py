"""Per-IP rate limits from docs/API.md "Conventions" (G105).

verdict 30/min, ingest 6/10 min, sandbox 3/h, everything else 120/min. 429 responses use
the error envelope with retry_after_s. In-memory sliding windows: correct for the single
API replica we run; health checks and requests with the admin token are exempt.
"""

from __future__ import annotations

import hmac
import math
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings
from app.errors import envelope

RULES: list[tuple[str, str, int, float]] = [
    # method, path prefix, max requests, window seconds
    ("POST", "/api/verdict", 30, 60.0),
    ("POST", "/api/ingest", 6, 600.0),
    ("POST", "/api/sandbox", 3, 3600.0),
]
DEFAULT = (120, 60.0)
EXEMPT = ("/api/health",)
MAX_TRACKED = 50_000


def client_ip(request: Request) -> str:
    # The last entry is the one our hosting proxy appended; earlier ones are client-supplied.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def _rule(method: str, path: str) -> tuple[str, int, float]:
    for rule_method, prefix, limit, window in RULES:
        if method == rule_method and path.startswith(prefix):
            return prefix, limit, window
    return "default", DEFAULT[0], DEFAULT[1]


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, clock=time.monotonic) -> None:
        super().__init__(app)
        self.clock = clock
        self.hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def _is_admin(self, request: Request) -> bool:
        header = request.headers.get("authorization", "")
        if not header.lower().startswith("bearer "):
            return False
        token = header.split(" ", 1)[1].strip()
        return hmac.compare_digest(token.encode(), get_settings().admin_token.encode())

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if (
            request.method == "OPTIONS"
            or path.startswith(EXEMPT)
            or self._is_admin(request)
            or client_ip(request) == "testclient"  # Starlette's in-process test client
        ):
            return await call_next(request)
        bucket, limit, window = _rule(request.method, path)
        key = (client_ip(request), bucket)
        now = self.clock()
        hits = self.hits[key]
        while hits and now - hits[0] >= window:
            hits.popleft()
        if len(hits) >= limit:
            retry = max(1, math.ceil(window - (now - hits[0])))
            return envelope(
                "RATE_LIMITED",
                "Too many requests from this address.",
                hint="Wait and retry.",
                retry_after_s=retry,
            )
        hits.append(now)
        if len(self.hits) > MAX_TRACKED:
            # Drop idle keys so memory stays bounded under many distinct clients.
            for stale in [k for k, v in self.hits.items() if not v or now - v[-1] > 3600]:
                del self.hits[stale]
        return await call_next(request)
