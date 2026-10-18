"""Verdicts are deterministic over Q1 and Q2. An LLM never changes the verdict."""

from __future__ import annotations

import json
import time
from typing import Any

import json

from app.engine.clauses import applies, obligation_status, parse_json_field, seed_path
from app.graph import db
from app.graph.queries import C3, Q1, Q2
from app.graph.rows import as_rows
from app.paths import repo_root

NO_ALTERNATIVES = "No compliant alternative in our candidate set."

DISCLAIMER = "Automated screening, not legal advice."


def summaries() -> dict[str, str]:
    seed = json.loads(seed_path().read_text())
    found: dict[str, str] = {}
    for licence in seed.get("licenses") or []:
        for clause in licence.get("clauses") or []:
            found[clause["id"]] = clause.get("summary") or ""
    return found


def decide(
    model_id: str,
    q1_rows: list[dict[str, Any]],
    q2_rows: list[dict[str, Any]],
    context: dict[str, Any],
    model: dict[str, Any],
) -> dict[str, Any]:
    """Apply FLOWS F1.7 to rows FalkorDB already returned."""
    summary = summaries()
    blocking: list[dict[str, Any]] = []
    obligations: list[dict[str, Any]] = []
    needs_counsel: list[dict[str, Any]] = []
    seen: set[str] = set()
    inherited: set[str] = set()
    own_key = ""
    unknown_on_path = False

    for row in q1_rows:
        licence = row.get("license") or None
        if licence in ("unknown", "other", "", None):
            unknown_on_path = True
        hops = int(row.get("hops") or 0)
        if hops == 0 and licence:
            own_key = str(licence)
        if hops > 0 and licence:
            inherited.add(str(licence))
        scope = dict(context)
        scope["ancestor_multimodal"] = bool(row.get("multimodal"))
        for raw in _clause_list(row.get("clauses")):
            clause_id = str(raw.get("id") or "")
            if not clause_id or clause_id in seen:
                continue
            effect = str(raw.get("effect") or "")
            rule = parse_json_field(raw.get("applies_when")) or {}
            if not isinstance(rule, dict) or not applies(rule, scope):
                continue
            seen.add(clause_id)
            quote = raw.get("quote") or None
            if quote == "":
                quote = None
            hit = _hit(raw, quote, summary, row, model)
            if quote is None or effect == "NEEDS_COUNSEL":
                hit["effect"] = "NEEDS_COUNSEL"
                needs_counsel.append(hit)
            elif effect == "BLOCK":
                blocking.append(hit)
            elif effect == "OBLIGATION":
                obligations.append(hit)

    incomplete = [row for row in q2_rows if not bool(row.get("is_root"))]
    reasons = [
        f"{row.get('top')} declares no parent and is not a known base model" for row in incomplete
    ]
    if not q1_rows:
        reasons.append(f"{model_id} is not in the hub")

    if blocking:
        verdict = "BLOCKED"
    elif incomplete or unknown_on_path or needs_counsel or not q1_rows:
        verdict = "CANNOT_DETERMINE"
    elif obligations:
        verdict = "ALLOWED_WITH_OBLIGATIONS"
    else:
        verdict = "ALLOWED"

    differs = bool(own_key) and any(
        key and key != own_key and _licence_is_serious(key, q1_rows) for key in inherited
    )

    return {
        "model_id": model_id,
        "verdict": verdict,
        "declared_license": model.get("declared_license") or None,
        "declared_differs": differs,
        "inherited_licenses": sorted(key for key in inherited if key),
        "blocking": blocking,
        "obligations": obligations,
        "needs_counsel": needs_counsel,
        "lineage_complete": not incomplete and bool(q1_rows),
        "incomplete_reasons": reasons,
        "disclaimer": DISCLAIMER,
    }


def _licence_is_serious(licence: str, rows: list[dict[str, Any]]) -> bool:
    for row in rows:
        if row.get("license") != licence:
            continue
        if int(row.get("hops") or 0) == 0:
            continue
        for raw in _clause_list(row.get("clauses")):
            if raw.get("effect") in ("BLOCK", "OBLIGATION"):
                return True
    return False


def _clause_list(value: Any) -> list[dict[str, Any]]:
    if not value:
        return []
    found = []
    for item in value:
        if isinstance(item, dict) and item.get("id"):
            found.append(item)
    return found


def _hit(
    raw: dict[str, Any],
    quote: str | None,
    summary: dict[str, str],
    row: dict[str, Any],
    model: dict[str, Any],
) -> dict[str, Any]:
    check = parse_json_field(raw.get("check"))
    hit: dict[str, Any] = {
        "clause_id": raw.get("id"),
        "kind": raw.get("kind") or "",
        "effect": raw.get("effect"),
        "license": row.get("license"),
        "quote": quote,
        "summary": summary.get(str(raw.get("id")), ""),
        "source_url": raw.get("source_url") or "",
        "section": raw.get("section") or "",
        "path": list(row.get("path") or []),
        "edge_tiers": [int(item) for item in (row.get("tiers") or [])],
        "relations": list(row.get("relations") or []),
    }
    if raw.get("effect") == "OBLIGATION" and quote is not None:
        hit["status"] = obligation_status(check if isinstance(check, dict) else None, model)
    return hit


def verdict_from_graph(
    model_id: str,
    context: dict[str, Any],
    *,
    graph: str = "hub",
    min_tier: int = 1,
) -> dict[str, Any]:
    started = time.perf_counter()
    q1 = as_rows(db.ro_query(graph, Q1, {"model_id": model_id, "min_tier": min_tier}))
    q2 = as_rows(db.ro_query(graph, Q2, {"model_id": model_id, "min_tier": min_tier}))
    props_rows = as_rows(db.ro_query(graph, C3, {"model_id": model_id}))
    model = props_rows[0] if props_rows else {}
    decided = decide(model_id, q1, q2, context, model)
    decided["paths"] = _paths(q1)
    decided["computed_ms"] = int((time.perf_counter() - started) * 1000)
    decided["strict"] = min_tier >= 2
    decided["context"] = context
    decided["alternatives"] = []
    decided["alternatives_message"] = None
    if decided["verdict"] == "BLOCKED":
        from app.engine.alternatives import find_alternatives

        alts, message = find_alternatives(
            context,
            graph=graph,
            min_tier=min_tier,
            pipeline_tag=str(model.get("pipeline_tag") or "") or None,
            exclude=model_id,
        )
        decided["alternatives"] = alts
        decided["alternatives_message"] = message
    decided["ruling_id"] = None
    decided["stale"] = False
    decided["explanation_source"] = "template"
    decided["explanation"] = explain_template(decided)
    decided["cypher"] = {"q1": Q1.strip(), "q2": Q2.strip()}
    return decided


def _paths(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for row in rows:
        path = tuple(str(item) for item in (row.get("path") or []))
        if not path or path in seen:
            continue
        seen.add(path)
        found.append(
            {
                "path": list(path),
                "tiers": [int(item) for item in (row.get("tiers") or [])],
                "relations": [str(item) for item in (row.get("relations") or [])],
            }
        )
    return found


def explain_template(decided: dict[str, Any]) -> str:
    verdict = str(decided["verdict"]).replace("_", " ")
    declared = decided.get("declared_license") or "no declared licence"
    inherited = ", ".join(decided.get("inherited_licenses") or []) or "nothing further"
    lines = [
        f"Verdict: {verdict}.",
        f"The card declares {declared}. Inherited licences: {inherited}.",
    ]
    if decided.get("declared_differs"):
        lines.append(
            "The declared licence differs from the obligations inherited from its ancestors."
        )
    for hit in (decided.get("blocking") or [])[:2]:
        lines.append(
            f"Blocking clause {hit.get('clause_id')}: {hit.get('summary') or hit.get('quote')}"
        )
    for hit in (decided.get("obligations") or [])[:3]:
        lines.append(f"Obligation {hit.get('clause_id')}: {hit.get('summary') or hit.get('quote')}")
    if decided.get("incomplete_reasons"):
        lines.append("Lineage notes: " + "; ".join(decided["incomplete_reasons"]))
    lines.append(DISCLAIMER)
    return " ".join(lines)
