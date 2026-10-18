"""Hidden-lineage resolver (FLOWS F4): WCC + inferred/mirror edges."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.graph import db
from app.graph.queries import R1, R2, R3
from app.graph.rows import as_rows

log = logging.getLogger("modelbrain.resolver")

_last_report: dict[str, Any] = {
    "at": None,
    "components": 0,
    "mirror": 0,
    "inferred_t1": 0,
    "inferred_t0": 0,
    "skipped": 0,
}


def last_report() -> dict[str, Any]:
    return dict(_last_report)


def _rule(shared: list[str]) -> tuple[str, float, int] | None:
    kinds = set(shared)
    if "weights_sha256" in kinds:
        return "mirror", 0.97, 1
    if "tokenizer_sha" in kinds and "config_fp" in kinds:
        return "inferred", 0.8, 1
    if "config_fp" in kinds:
        return "inferred", 0.5, 0
    return None


def _has_outgoing(graph: str, model_id: str) -> bool:
    rows = as_rows(
        db.ro_query(
            graph,
            "MATCH (m:Model {id: $id})-[:DERIVED_FROM]->() RETURN count(*) AS n",
            {"id": model_id},
        )
    )
    return bool(rows and int(rows[0].get("n") or 0) > 0)


def _is_root(graph: str, model_id: str) -> bool:
    rows = as_rows(
        db.ro_query(
            graph,
            "MATCH (m:Model {id: $id}) RETURN coalesce(m.is_root, false) AS is_root",
            {"id": model_id},
        )
    )
    return bool(rows and rows[0].get("is_root"))


def run_resolver(graph: str = "hub") -> dict[str, Any]:
    report = {
        "at": int(time.time() * 1000),
        "components": 0,
        "mirror": 0,
        "inferred_t1": 0,
        "inferred_t0": 0,
        "skipped": 0,
        "edges": [],
    }
    try:
        components = as_rows(db.ro_query(graph, R1))
    except Exception as exc:
        log.warning("R1 WCC failed: %s", exc)
        components = []
    report["components"] = len(components)
    for row in components:
        model_ids = [str(m) for m in (row.get("model_ids") or []) if m]
        for model_id in model_ids:
            if _is_root(graph, model_id) or _has_outgoing(graph, model_id):
                continue
            candidates = as_rows(db.ro_query(graph, R2, {"model_id": model_id}))
            if not candidates:
                report["skipped"] += 1
                continue
            chosen = candidates[0]
            parent = str(chosen.get("root") or "")
            shared = [str(k) for k in (chosen.get("shared_kinds") or [])]
            rule = _rule(shared)
            if not rule or not parent:
                report["skipped"] += 1
                continue
            relation, conf, tier = rule
            evidence = f"shared {'+'.join(shared)} with {parent}"
            db.query(
                graph,
                R3,
                {
                    "child": model_id,
                    "parent": parent,
                    "relation": relation,
                    "conf": conf,
                    "tier": tier,
                    "evidence": evidence,
                },
            )
            report["edges"].append(
                {"child": model_id, "parent": parent, "relation": relation, "tier": tier}
            )
            if relation == "mirror":
                report["mirror"] += 1
            elif tier == 1:
                report["inferred_t1"] += 1
            else:
                report["inferred_t0"] += 1
    global _last_report
    _last_report = report
    log.info("resolver done: %s", {k: report[k] for k in report if k != "edges"})
    return report


# Licence keys a card can carry that impose no field-of-use, geography or attribution terms
# beyond a notice. A permissive card over a restrictive ancestor is a relabel.
PERMISSIVE = (
    "apache-2.0",
    "mit",
    "bsd-2-clause",
    "bsd-3-clause",
    "cc-by-4.0",
    "cc-by-sa-4.0",
    "cc0-1.0",
    "wtfpl",
    "unlicense",
)


def set_declared_differs(graph: str = "hub") -> int:
    """G059: flag models whose declared licence differs from an inherited ancestor licence.

    Compares normalised licence keys (the card's raw string, e.g. "llama3.1", never matched
    the key "llama3_1", so nearly every model was flagged), over trusted edges only.
    """
    from app.graph.queries import X16, X17

    rows = as_rows(db.ro_query(graph, X16, {"permissive": list(PERMISSIVE)}))
    ids = sorted({str(r["id"]) for r in rows if r.get("id")})
    db.query(graph, X17, {"ids": ids})
    return len(ids)
