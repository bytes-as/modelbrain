"""JSON logs with a request id. Secret values are never written."""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_SECRET_ENV = (
    "ADMIN_TOKEN",
    "PUBLISHER_SALT",
    "HF_TOKEN",
    "HF_WRITE_TOKEN",
    "OPENROUTER_API_KEY",
    "FIRECRAWL_API_KEY",
    "ANAKIN_API_KEY",
    "FALKORDB_PASSWORD",
)


def scrub(text: str) -> str:
    redacted = text
    for key in _SECRET_ENV:
        secret = os.environ.get(key, "").strip()
        if secret and secret in redacted:
            redacted = redacted.replace(secret, "[redacted]")
    return redacted


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": scrub(record.getMessage()),
            "request_id": getattr(record, "request_id", None) or request_id_var.get(),
        }
        if record.exc_info:
            payload["exc"] = scrub(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True


class OriginAllowlistMiddleware(BaseHTTPMiddleware):
    """Reject browser calls whose Origin is outside CORS_ORIGINS."""

    def __init__(self, app: object, origins: list[str]) -> None:
        super().__init__(app)
        self.origins = set(origins)

    async def dispatch(self, request: Request, call_next) -> Response:
        origin = request.headers.get("origin")
        if origin and origin not in self.origins:
            return Response("Disallowed CORS origin", status_code=400, media_type="text/plain")
        return await call_next(request)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get("x-request-id", "").strip()
        request_id = incoming or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        request.state.request_id = request_id
        try:
            response = await call_next(request)
            response.headers["X-Request-Id"] = request_id
            logging.getLogger("modelbrain.access").info(
                "%s %s %s", request.method, request.url.path, response.status_code
            )
            return response
        finally:
            request_id_var.reset(token)
