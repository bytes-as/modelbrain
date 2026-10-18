"""Hosted path: who serves a model through an API, from where (FLOWS F16, G128-G131).

Public OpenRouter catalogue, no key needed. Providers, hosted models and endpoints become
(:Provider)-[:SERVES]->(:HostedModel)-[:IS]->(:Model) in the hub, so the same graph that
walks a model's licence lineage also answers "which provider can serve it from the EU?".
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.graph import db
from app.graph.queries import O1, O2, O3, O4, X23
from app.graph.rows import as_rows
from app.hf.cache import DiskCache
from app.hf.client import HFClient
from app.paths import repo_root

log = logging.getLogger("modelbrain.hosted")
OR = "https://openrouter.ai/api/v1"
_last_sync: dict[str, Any] = {}


def _client() -> HFClient:
    # The HF client is a generic cached, rate-limited, retrying HTTP client.
    return HFClient(cache=DiskCache(Path("/tmp/modelbrain-openrouter")))


def eu_countries() -> list[str]:
    data = json.loads((repo_root() / "data" / "eu_countries.json").read_text())
    return [str(c).upper() for c in data["EU"]]


async def sync_catalog(graph: str = "hub") -> dict[str, Any]:
    client = _client()
    now = int(time.time() * 1000)
    report = {"providers": 0, "hosted_models": 0}
    try:
        providers = await client.get_json(f"{OR}/providers")
        for p in (providers or {}).get("data", []) if isinstance(providers, dict) else []:
            db.query(
                graph,
                O1,
                {
                    "slug": str(p.get("slug") or ""),
                    "name": str(p.get("name") or ""),
                    "hq": p.get("headquarters"),
                    "datacenters": [str(c).upper() for c in (p.get("datacenters") or [])],
                    "tos_url": p.get("terms_of_service_url"),
                    "privacy_url": p.get("privacy_policy_url"),
                    "now": now,
                },
            )
            report["providers"] += 1
        models = await client.get_json(f"{OR}/models")
        for m in (models or {}).get("data", []) if isinstance(models, dict) else []:
            hf_id = m.get("hugging_face_id")
            if not hf_id or "/" not in str(hf_id):
                continue
            db.query(
                graph,
                O2,
                {"or_id": m["id"], "name": m.get("name") or m["id"], "hf_id": hf_id, "now": now},
            )
            report["hosted_models"] += 1
    finally:
        await client.aclose()
    _last_sync.clear()
    _last_sync.update({**report, "at": now})
    log.info("openrouter catalogue synced", extra=report)
    return report


async def sync_endpoints(or_id: str, graph: str = "hub") -> int:
    client = _client()
    try:
        data = await client.get_json(f"{OR}/models/{or_id}/endpoints")
    finally:
        await client.aclose()
    endpoints = (
        ((data or {}).get("data") or {}).get("endpoints", []) if isinstance(data, dict) else []
    )
    for e in endpoints:
        tag = str(e.get("tag") or "")
        db.query(
            graph,
            O3,
            {
                "or_id": or_id,
                "provider_slug": tag.split("/")[0],
                "quantization": e.get("quantization"),
                "tag": tag,
                "status": e.get("status"),
                "uptime_30m": e.get("uptime_last_30m"),
            },
        )
    return len(endpoints)


async def where_can_i_run(
    hf_id: str, residency: str | list[str] | None, graph: str = "hub", *, refresh: bool = True
) -> dict[str, Any]:
    """Hosted models backed by these weights, the providers serving them, and the residency proof."""
    if residency == "EU":
        allowed: list[str] | None = eu_countries()
    elif isinstance(residency, list):
        allowed = [c.upper() for c in residency]
    else:
        allowed = None
    if refresh:
        for row in as_rows(db.ro_query(graph, X23, {"hf_id": hf_id})):
            try:
                await sync_endpoints(str(row["or_id"]), graph)
            except Exception:
                log.warning("endpoint sync failed", extra={"or_id": row["or_id"]})
    out: list[dict[str, Any]] = []
    for row in as_rows(db.ro_query(graph, X23, {"hf_id": hf_id})):
        or_id = str(row["or_id"])
        ok = (
            as_rows(db.ro_query(graph, O4, {"or_id": or_id, "allowed_countries": allowed}))
            if allowed
            else []
        )
        providers = [p for p in (row.get("providers") or []) if p]
        out.append({"or_id": or_id, "name": row.get("name"), "providers": providers, "allowed": ok})
    result: dict[str, Any] = {"model_id": hf_id, "hosted": out}
    if allowed is not None:
        any_ok = any(item["allowed"] for item in out)
        result["residency"] = {
            "requested": residency,
            "ok": any_ok,
            "proof": None if any_ok else "no provider serves this model from an allowed datacenter",
        }
    return result


def hosted_adjust(decided: dict[str, Any], end_user_only: bool) -> dict[str, Any]:
    """Through a provider the weights are not distributed; the EU multimodal exclusion has an
    end-user exemption, so for hosted use it becomes NEEDS_COUNSEL unless end_user_only is set."""
    blocking = list(decided.get("blocking") or [])
    moved = [b for b in blocking if str(b.get("clause_id", "")).endswith("geo_eu_multimodal")]
    if not moved:
        return decided
    rest = [b for b in blocking if b not in moved]
    counsel = list(decided.get("needs_counsel") or [])
    if not end_user_only:
        for hit in moved:
            counsel.append(
                {
                    **hit,
                    "effect": "NEEDS_COUNSEL",
                    "summary": (
                        "You call the model through a provider; whether the exemption for end users "
                        "covers your product needs counsel."
                    ),
                }
            )
    decided = {**decided, "blocking": rest, "needs_counsel": counsel}
    if not rest:
        decided["verdict"] = (
            "CANNOT_DETERMINE"
            if counsel
            else ("ALLOWED_WITH_OBLIGATIONS" if decided.get("obligations") else "ALLOWED")
        )
    return decided


def last_sync() -> dict[str, Any]:
    return dict(_last_sync)


def refresh_hours() -> int:
    return max(get_settings().openrouter_catalog_refresh_hours, 1)
