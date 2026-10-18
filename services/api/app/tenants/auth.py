"""Tenant token checks. Fixed tenants are read-only for visitors."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from app.config import get_settings
from app.errors import ApiError
from app.tenants.bootstrap import TENANTS

_sandbox_tokens: dict[str, dict[str, object]] = {}


def register_sandbox(name: str, token: str, *, template: str, expires_at: int) -> None:
    _sandbox_tokens[name] = {
        "token_hash": _hash(token),
        "template": template,
        "expires_at": expires_at,
    }


def restore_sandbox(name: str, token_hash: str, *, template: str, expires_at: int) -> None:
    """Re-register a sandbox from its persisted hash after an API restart."""
    _sandbox_tokens[name] = {
        "token_hash": token_hash,
        "template": template,
        "expires_at": expires_at,
    }


def token_hash(token: str) -> str:
    return _hash(token)


def drop_sandbox(name: str) -> None:
    _sandbox_tokens.pop(name, None)


def list_sandbox_registry() -> dict[str, dict[str, object]]:
    return dict(_sandbox_tokens)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _const_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def require_admin(authorization: str | None) -> None:
    settings = get_settings()
    if not authorization or not authorization.lower().startswith("bearer "):
        raise ApiError("UNAUTHORIZED", "Admin token required.")
    token = authorization.split(" ", 1)[1].strip()
    if not _const_eq(token, settings.admin_token):
        raise ApiError("UNAUTHORIZED", "Admin token required.")


def resolve_tenant(
    tenant: str,
    *,
    token: str | None = None,
    authorization: str | None = None,
    write: bool = False,
) -> str:
    """Return the graph name. Fixed tenants reject writes unless admin."""
    if tenant in TENANTS:
        if write:
            try:
                require_admin(authorization)
            except ApiError:
                raise ApiError(
                    "READ_ONLY_TENANT",
                    "Fixed demo tenants are read-only. Create a sandbox to write.",
                    hint="POST /api/sandbox",
                ) from None
        return tenant
    if not tenant.startswith("sbx_"):
        raise ApiError("MODEL_NOT_FOUND", f"No tenant '{tenant}'.")
    record = _sandbox_tokens.get(tenant)
    if record is None:
        raise ApiError(
            "SANDBOX_EXPIRED", "Sandbox not found or expired.", hint="Create a new sandbox."
        )
    import time

    if int(record["expires_at"]) < int(time.time() * 1000):
        raise ApiError("SANDBOX_EXPIRED", "Sandbox expired.", hint="Create a new sandbox.")
    if write or token is not None:
        if not token or not _const_eq(_hash(token), str(record["token_hash"])):
            # also accept admin bearer
            try:
                require_admin(authorization)
            except ApiError:
                raise ApiError("UNAUTHORIZED", "Sandbox token required.") from None
    return tenant


def new_token() -> str:
    return secrets.token_urlsafe(32)
