"""Reverse fan-out, reopen and compounding (FLOWS F8, F9, F11).

A change to one hub model (new revision, licence file added, edge tier raised)
walks down the lineage with D1, finds every active ruling in every company
graph that rests on any affected model (T3), and reopens each one as an Event
plus a review Task for the deployment owner (T4). Nothing is overwritten:
rulings stay append-only and the owner approves a superseding ruling.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any

from app.config import get_settings
from app.graph import db
from app.graph.queries import D1, D2, P1, T3, T4, X1, X2, X3, X4, X6, X14
from app.graph.rows import as_rows
from app.graph.schema import graph_names
from app.ids import new_id
from app.paths import repo_root

log = logging.getLogger("modelbrain.watcher")


def _now_ms() -> int:
    return int(time.time() * 1000)


def company_graphs(*, include_fixed: bool = True) -> list[str]:
    """Company graphs. Visitor-triggered fan-outs pass include_fixed=False so the
    read-only demo companies only change through admin actions."""
    prefixes = ("tenant_", "sbx_") if include_fixed else ("sbx_",)
    return [name for name in graph_names() if name.startswith(prefixes)]


def descendants(model_id: str, hub: str = "hub") -> list[str]:
    return [str(r["id"]) for r in as_rows(db.ro_query(hub, D1, {"model_id": model_id}))]


def leverage(model_id: str, hub: str = "hub") -> dict[str, int]:
    rows = as_rows(db.ro_query(hub, D2, {"model_id": model_id}))
    if not rows:
        return {"descendants": 0, "not_inherited": 0}
    return {
        "descendants": int(rows[0].get("descendants") or 0),
        "not_inherited": int(rows[0].get("not_inherited") or 0),
    }


def affected_rulings(model_id: str, graphs: list[str], hub: str = "hub") -> list[dict[str, Any]]:
    """Read-only: which active rulings would reopen if `model_id` changed."""
    affected = [model_id, *descendants(model_id, hub)]
    found: list[dict[str, Any]] = []
    for graph in graphs:
        for row in as_rows(db.ro_query(graph, T3, {"model_ids": affected})):
            found.append({"graph": graph, **row})
    return found


def fan_out(
    model_id: str,
    reason: str,
    *,
    graphs: list[str] | None = None,
    hub: str = "hub",
    include_fixed: bool = True,
) -> dict[str, Any]:
    started = time.monotonic()
    down = descendants(model_id, hub)
    lev = leverage(model_id, hub)
    targets = company_graphs(include_fixed=include_fixed) if graphs is None else graphs
    affected = [model_id, *down]
    reopened: list[dict[str, Any]] = []
    for graph in targets:
        try:
            rows = as_rows(db.ro_query(graph, T3, {"model_ids": affected}))
        except Exception:
            log.exception("fan-out read failed", extra={"graph": graph, "model_id": model_id})
            continue
        for row in rows:
            task_id = new_id("task")
            db.query(
                graph,
                T4,
                {
                    "ruling_id": row["ruling_id"],
                    "owner_id": row["owner_id"],
                    "event_id": new_id("evt"),
                    "task_id": task_id,
                    "now": _now_ms(),
                    "reason": reason,
                },
            )
            reopened.append(
                {
                    "graph": graph,
                    "ruling_id": row["ruling_id"],
                    "deployment_id": row["deployment_id"],
                    "owner_id": row["owner_id"],
                    "affected_models": row.get("affected_models") or [],
                    "task_id": task_id,
                }
            )
    report = {
        "id": new_id("fan"),
        "model_id": model_id,
        "reason": reason,
        "descendants": len(down),
        "descendant_ids": down,
        "not_inherited": lev["not_inherited"],
        "graphs": targets,
        "reopened": reopened,
        "ms": int((time.monotonic() - started) * 1000),
    }
    db.query(
        hub,
        X1,
        {
            "id": report["id"],
            "model_id": model_id,
            "reason": reason,
            "now": _now_ms(),
            "descendants": len(down),
            "not_inherited": lev["not_inherited"],
            "reopened": len(reopened),
            "graphs": targets,
        },
    )
    log.info(
        "fan-out",
        extra={"model_id": model_id, "descendants": len(down), "reopened": len(reopened)},
    )
    return report


def recent_fan_outs(limit: int = 20, hub: str = "hub") -> list[dict[str, Any]]:
    return as_rows(db.ro_query(hub, X4, {"limit": limit}))


# --- compounding (Publisher) ---------------------------------------------------


def tenant_hash(tenant: str) -> str:
    salt = get_settings().publisher_salt.encode("utf-8")
    return hmac.new(salt, tenant.encode("utf-8"), hashlib.sha256).hexdigest()[:24]


def edge_state(child: str, parent: str, hub: str = "hub") -> dict[str, Any] | None:
    rows = as_rows(db.ro_query(hub, X3, {"child": child, "parent": parent}))
    return rows[0] if rows else None


def confirm_edge(
    tenant_graph: str,
    child: str,
    parent: str,
    person_id: str,
    *,
    hub: str = "hub",
    include_fixed: bool = True,
    graphs: list[str] | None = None,
) -> dict[str, Any]:
    """Record a company's confirmation privately, publish only a salted hash, reopen on a tier change."""
    before = edge_state(child, parent, hub)
    if before is None:
        return {"ok": False, "reason": "no such edge in the hub", "child": child, "parent": parent}
    event = as_rows(
        db.query(
            tenant_graph,
            X2,
            {
                "person_id": person_id,
                "event_id": new_id("evt"),
                "now": _now_ms(),
                "child": child,
                "parent": parent,
            },
        )
    )
    if not event:
        return {"ok": False, "reason": "unknown person in this company", "person_id": person_id}
    after = as_rows(
        db.query(
            hub, P1, {"child": child, "parent": parent, "tenant_hash": tenant_hash(tenant_graph)}
        )
    )[0]
    result: dict[str, Any] = {
        "ok": True,
        "child": child,
        "parent": parent,
        "tier_before": int(before["tier"] or 0),
        "tier_after": int(after["tier"] or 0),
        "confirmations": int(after["confirmations"] or 0),
    }
    if result["tier_after"] > result["tier_before"]:
        result["fan_out"] = fan_out(
            child,
            f"lineage edge {child} -> {parent} confirmed by two independent companies "
            f"(tier {result['tier_before']} -> {result['tier_after']})",
            hub=hub,
            include_fixed=include_fixed,
            graphs=graphs,
        )
    return result


# --- Xkev replay -------------------------------------------------------------


def replay_data() -> dict[str, Any]:
    return json.loads((repo_root() / "data" / "replay_xkev.json").read_text())


def replay_view(hub: str = "hub") -> dict[str, Any]:
    data = replay_data()
    model_id = data["model_id"]
    graphs = [name for name in company_graphs() if name.startswith("tenant_")]
    return {
        **data,
        "graph_descendants": descendants(model_id, hub),
        "leverage": leverage(model_id, hub),
        "would_reopen": affected_rulings(model_id, graphs, hub),
    }


def run_replay(graph: str, hub: str = "hub") -> dict[str, Any]:
    data = replay_data()
    fix = data["fix"]
    reason = (
        f"Replay: {data['model_id']} added LICENSE_llama.txt on {fix['date']} "
        f"(commit {fix['commit']}), {fix['days_after_report']} days after the licence question"
    )
    return fan_out(data["model_id"], reason, graphs=[graph], hub=hub)


# --- compounding demo -----------------------------------------------------------

DEMO_EDGE = ("SicariusSicariiStuff/Llama-3.2-1B_Base_FP8", "meta-llama/Llama-3.2-1B")
DEMO_FIRST_CONFIRMER = "tenant_harbor"


def reset_compounding_demo(hub: str = "hub") -> dict[str, Any]:
    """Start state for the demo: one company (Harbor, fictional) has confirmed the edge, tier 1.

    A visitor's sandbox confirmation is then the second independent one and lifts it to tier 3.
    """
    child, parent = DEMO_EDGE
    rows = as_rows(
        db.query(
            hub,
            X6,
            {
                "child": child,
                "parent": parent,
                "confirmers": [tenant_hash(DEMO_FIRST_CONFIRMER)],
                "tier": 1,
            },
        )
    )
    if not rows:
        return {"ok": False, "reason": "demo edge not in the hub yet; run the resolver first"}
    return {"ok": True, "child": child, "parent": parent, **rows[0]}


# --- check now (FLOWS F9.1-6) -----------------------------------------------------

WATCHED = ("sha", "declared_license", "has_license_file", "card_has_llama_notice")


def model_state(model_id: str, hub: str = "hub") -> dict[str, Any] | None:
    rows = as_rows(db.ro_query(hub, X14, {"id": model_id}))
    return rows[0] if rows else None


def diff_states(before: dict[str, Any] | None, after: dict[str, Any] | None) -> list[str]:
    if before is None or after is None:
        return []
    return [
        f"{key}: {before.get(key)!r} -> {after.get(key)!r}"
        for key in WATCHED
        if before.get(key) != after.get(key)
    ]


async def check_now(
    model_id: str, reingest: Any, *, graphs: list[str] | None = None, hub: str = "hub"
) -> dict[str, Any]:
    """Re-read a model from the Hub (no cache), diff the facts, fan out only on a change."""
    before = model_state(model_id, hub)
    await reingest(model_id)
    after = model_state(model_id, hub)
    changes = diff_states(before, after)
    result: dict[str, Any] = {
        "model_id": model_id,
        "changed": bool(changes),
        "changes": changes,
        "sha": (after or {}).get("sha"),
    }
    if changes:
        result["fan_out"] = fan_out(
            model_id, "upstream change: " + "; ".join(changes), graphs=graphs, hub=hub
        )
    return result
