"""Error envelope from docs/API.md Conventions."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("modelbrain.errors")

CODES: dict[str, int] = {
    "INVALID_INPUT": 422,
    "MODEL_NOT_FOUND": 404,
    "UNAUTHORIZED": 401,
    "SANDBOX_EXPIRED": 401,
    "READ_ONLY_TENANT": 403,
    "NOT_ALLOWLISTED": 403,
    "STALE_RULING": 409,
    "RATE_LIMITED": 429,
    "GRAPH_UNAVAILABLE": 503,
    "HUB_UNAVAILABLE": 503,
    "INTERNAL": 500,
}


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        hint: str | None = None,
        retry_after_s: int | None = None,
    ) -> None:
        if code not in CODES:
            raise ValueError(f"unknown error code {code}")
        self.code = code
        self.message = message
        self.hint = hint
        self.retry_after_s = retry_after_s
        self.status = CODES[code]
        super().__init__(message)


def envelope(
    code: str,
    message: str,
    *,
    hint: str | None = None,
    retry_after_s: int | None = None,
) -> JSONResponse:
    status = CODES[code]
    body = {
        "error": {
            "code": code,
            "message": message,
            "hint": hint,
            "retry_after_s": retry_after_s,
        }
    }
    headers = {}
    if retry_after_s is not None:
        headers["Retry-After"] = str(retry_after_s)
    return JSONResponse(status_code=status, content=body, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(_request: Request, exc: ApiError) -> JSONResponse:
        log.info("api error %s", exc.code)
        return envelope(
            exc.code,
            exc.message,
            hint=exc.hint,
            retry_after_s=exc.retry_after_s,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = []
        for err in exc.errors():
            loc = [str(part) for part in err.get("loc", []) if part not in ("body", "query")]
            if loc:
                fields.append(".".join(loc))
        hint = f"Check: {', '.join(fields)}." if fields else "Check the request body."
        return envelope("INVALID_INPUT", "Request failed validation.", hint=hint)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            return envelope(
                "MODEL_NOT_FOUND",
                "Not found.",
                hint="Check the id, e.g. meta-llama/Llama-3.2-1B.",
            )
        if exc.status_code == 422:
            return envelope("INVALID_INPUT", "Request failed validation.")
        log.info("http error %s", exc.status_code)
        return envelope("INTERNAL", "Request failed.")

    @app.exception_handler(Exception)
    async def unhandled(_request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error: %s", type(exc).__name__)
        return envelope("INTERNAL", "Something went wrong.")
