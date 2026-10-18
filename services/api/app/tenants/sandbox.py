"""Visitor sandboxes via GRAPH.COPY (FLOWS F7)."""

from __future__ import annotations

import logging
import time
import uuid

from app.config import get_settings
from app.errors import ApiError
from app.graph import db
from app.tenants.auth import (
    drop_sandbox,
    list_sandbox_registry,
    new_token,
    register_sandbox,
)

log = logging.getLogger("modelbrain.sandbox")

MAX_LIVE = 50
TEMPLATES = ("kestrel", "harbor")


def create_sandbox(template: str) -> dict[str, object]:
    if template not in TEMPLATES:
        raise ApiError("INVALID_INPUT", "template must be kestrel or harbor.")
    settings = get_settings()
    live = list_sandbox_registry()
    if len(live) >= MAX_LIVE:
        oldest = sorted(live.items(), key=lambda item: int(item[1]["expires_at"]))[0][0]
        delete_sandbox(oldest)
    source = f"tenant_{template}"
    for _ in range(2):
        name = f"sbx_{uuid.uuid4().hex[:8]}"
        try:
            db.copy_graph(source, name)
        except Exception as exc:
            if "already" in str(exc).lower() or "exists" in str(exc).lower():
                continue
            raise ApiError("GRAPH_UNAVAILABLE", "Could not copy tenant graph.") from exc
        token = new_token()
        expires_at = int(time.time() * 1000) + settings.sandbox_ttl_minutes * 60_000
        register_sandbox(name, token, template=template, expires_at=expires_at)
        try:
            from app.tenants.playbooks import seed_playbooks

            seed_playbooks(name)
        except Exception:
            log.warning("playbook seed failed for %s", name)
        try:
            db.query(
                "hub",
                "MERGE (s:Sandbox {name: $name}) SET s.expires_at = $expires_at",
                {"name": name, "expires_at": expires_at},
            )
        except Exception:
            log.warning("hub Sandbox registry write failed for %s", name)
        return {"tenant": name, "token": token, "expires_at": expires_at}
    raise ApiError("INTERNAL", "Could not allocate a sandbox id.")


def delete_sandbox(name: str) -> None:
    drop_sandbox(name)
    try:
        db.delete_graph(name)
    except Exception:
        log.warning("GRAPH.DELETE failed for %s", name)
    try:
        db.query("hub", "MATCH (s:Sandbox {name: $name}) DELETE s", {"name": name})
    except Exception:
        pass


def cleanup_expired() -> int:
    now = int(time.time() * 1000)
    removed = 0
    for name, record in list(list_sandbox_registry().items()):
        if int(record["expires_at"]) < now:
            delete_sandbox(name)
            removed += 1
    return removed
