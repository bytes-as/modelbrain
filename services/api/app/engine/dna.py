"""Weight DNA in the graph: writes, foundation references, resolver step, merge fit, crawl.

ADDENDUM_WEIGHT_DNA sections 3, 4, 6 and 10. FalkorDB does the similarity
search (W2), stores every edge and answers every read; Python only validates
vectors and solves the 2x2 least-squares merge fit.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
import math
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.graph import db
from app.graph.queries import R3, W0, W1, W1B, W2, W3, W7, W10, W11, W12, W13, W14, W15, X5
from app.graph.rows import as_rows
from app.hf.cache import DiskCache
from app.hf.client import HFClient, HubUnavailable
from app.hf.dna import ERROR, OK, DnaError, DnaResult, Sampler, validate_vector
from app.paths import repo_root

log = logging.getLogger("modelbrain.dna")

MERGE_MIN_SHARE = 0.10
MERGE_SUM = (0.90, 1.10)
MERGE_MIN_R2 = 0.995
MERGE_TOP = 5
# A merge must explain what no single parent can. Measured on real models (2x512 values):
# the verified 0.6/0.4 linear merge leaves 0.06-0.09% unexplained by its best single parent
# and two parents remove 99.2-99.5% of that; near-identical swarm copies leave ~0.002% and
# two "parents" remove at most 53%; plain fine-tunes remove 0-6%.
MERGE_MIN_RESIDUAL = 0.0001
MERGE_MIN_REDUCTION = 0.95
TIE_SIM = 0.0005

_last: dict[str, Any] = {}
_crawl: dict[str, Any] = {"state": "idle"}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def dimension() -> int:
    return 2 * get_settings().dna_per_tensor


def ensure_index(graph: str = "hub") -> None:
    try:
        db.query(graph, W0)
    except Exception as exc:
        if "already indexed" not in str(exc).lower():
            raise


# --- writes -----------------------------------------------------------------


def write_result(graph: str, model_id: str, result: DnaResult) -> str:
    """Write a fingerprint (W1) or a non-OK status (W1B). Returns the status written."""
    if result.status == OK:
        try:
            validate_vector(result.vector, dimension())
        except DnaError as exc:
            log.error("refused fingerprint", extra={"model_id": model_id, "reason": exc.reason})
            db.query(graph, W1B, {"id": model_id, "status": ERROR, "now": _now()})
            return ERROR
        db.query(
            graph,
            W1,
            {
                "id": model_id,
                "dna": [float(x) for x in result.vector],
                "sig": result.sig,
                "now": _now(),
            },
        )
        return OK
    db.query(graph, W1B, {"id": model_id, "status": result.status, "now": _now()})
    return result.status


# --- references -------------------------------------------------------------


def references() -> list[dict[str, str]]:
    data = json.loads((repo_root() / "data" / "dna_references.json").read_text())
    return [
        {"id": str(item["id"]), "fingerprint_from": str(item.get("fingerprint_from") or item["id"])}
        for item in data.get("foundations", [])
    ]


def mark_references(graph: str = "hub") -> int:
    ids = [ref["id"] for ref in references()]
    rows = as_rows(db.query(graph, W10, {"ids": ids}))
    return int(rows[0]["marked"]) if rows else 0


def inherit_mirror_fingerprints(graph: str = "hub") -> int:
    """Gated official repos hide config.json; borrow the config fingerprint of the public mirror."""
    copied = 0
    for ref in references():
        if ref["fingerprint_from"] == ref["id"]:
            continue
        rows = as_rows(
            db.query(graph, X5, {"mirror": ref["fingerprint_from"], "official": ref["id"]})
        )
        copied += int(rows[0]["copied"]) if rows else 0
    return copied


# --- merge fit ----------------------------------------------------------------


def single_r2(child: list[float], p: list[float]) -> float:
    """R2 of the best scaled single parent: child ~ a*p."""
    spp = sum(x * x for x in p)
    tot = sum(x * x for x in child)
    if spp == 0 or tot == 0:
        return 0.0
    scp = sum(x * y for x, y in zip(child, p, strict=True))
    return (scp * scp) / (spp * tot)


def fit_pair(child: list[float], p: list[float], q: list[float]) -> tuple[float, float, float]:
    """Least squares child ~ a*p + b*q. Returns (a, b, r2)."""
    spp = sum(x * x for x in p)
    sqq = sum(x * x for x in q)
    spq = sum(x * y for x, y in zip(p, q, strict=True))
    scp = sum(x * y for x, y in zip(child, p, strict=True))
    scq = sum(x * y for x, y in zip(child, q, strict=True))
    tot = sum(x * x for x in child)
    det = spp * sqq - spq * spq
    if tot == 0 or abs(det) < 1e-12 * max(spp * sqq, 1e-30):
        return 0.0, 0.0, 0.0
    a = (scp * sqq - scq * spq) / det
    b = (scq * spp - scp * spq) / det
    res = sum((c - a * x - b * y) ** 2 for c, x, y in zip(child, p, q, strict=True))
    return a, b, 1.0 - res / tot


def best_merge(
    child: list[float], candidates: dict[str, list[float]], per_tensor: int
) -> dict[str, Any] | None:
    """Try each pair of candidates, window by window; return the accepted pair with the best R2."""
    best: dict[str, Any] | None = None
    windows = [(0, per_tensor), (per_tensor, 2 * per_tensor)]
    for pid, qid in itertools.combinations(list(candidates)[:MERGE_TOP], 2):
        p, q = candidates[pid], candidates[qid]
        fits = [fit_pair(child[s:e], p[s:e], q[s:e]) for s, e in windows]
        singles = [
            max(single_r2(child[s:e], p[s:e]), single_r2(child[s:e], q[s:e])) for s, e in windows
        ]
        ok = all(
            a >= MERGE_MIN_SHARE
            and b >= MERGE_MIN_SHARE
            and MERGE_SUM[0] <= a + b <= MERGE_SUM[1]
            and r2 >= MERGE_MIN_R2
            and (1.0 - one) >= MERGE_MIN_RESIDUAL
            and (1.0 - r2) <= (1.0 - MERGE_MIN_REDUCTION) * (1.0 - one)
            for (a, b, r2), one in zip(fits, singles, strict=True)
        )
        if not ok:
            continue
        mean_a = sum(f[0] for f in fits) / len(fits)
        mean_b = sum(f[1] for f in fits) / len(fits)
        mean_r2 = sum(f[2] for f in fits) / len(fits)
        total = mean_a + mean_b
        found = {
            "parents": [
                {"id": pid, "share": round(mean_a / total, 4)},
                {"id": qid, "share": round(mean_b / total, 4)},
            ],
            "r2": round(mean_r2, 6),
            "windows": [[round(a, 4), round(b, 4), round(r2, 6)] for a, b, r2 in fits],
        }
        if best is None or found["r2"] > best["r2"]:
            best = found
    return best


# --- resolver step ------------------------------------------------------------


def _references_among(graph: str, ids: list[str]) -> set[str]:
    rows = as_rows(db.ro_query(graph, W15, {"ids": ids}))
    return {str(r["id"]) for r in rows}


def _vectors(graph: str, ids: list[str]) -> dict[str, list[float]]:
    rows = as_rows(db.ro_query(graph, W11, {"ids": ids}))
    return {str(r["id"]): [float(x) for x in (r["dna"] or [])] for r in rows}


def resolve_model(graph: str, model_id: str) -> dict[str, Any] | None:
    settings = get_settings()
    rows = as_rows(
        db.ro_query(graph, W2, {"id": model_id, "k": 50, "min_sim": settings.dna_related_min})
    )
    if not rows:
        return None
    if len(rows) >= 2:
        vectors = _vectors(graph, [model_id, *[str(r["parent"]) for r in rows]])
        child = vectors.get(model_id)
        candidates = {
            str(r["parent"]): vectors[str(r["parent"])] for r in rows if str(r["parent"]) in vectors
        }
        if child and len(candidates) >= 2:
            merge = best_merge(child, candidates, settings.dna_per_tensor)
            if merge:
                sims = {str(r["parent"]): float(r["sim"]) for r in rows}
                tier = (
                    1
                    if all(
                        sims.get(p["id"], 0.0) >= settings.dna_related_min for p in merge["parents"]
                    )
                    else 0
                )
                pa, pb = merge["parents"]
                evidence = (
                    f"merge fit: {pa['share']:.2f} x {pa['id']} + {pb['share']:.2f} x {pb['id']}, "
                    f"R2 {merge['r2']:.4f} (o_proj and down_proj windows)"
                )
                db.query(
                    graph,
                    W7,
                    {
                        "child": model_id,
                        "tier": tier,
                        "parents": [
                            {
                                "id": p["id"],
                                "share": p["share"],
                                "r2": merge["r2"],
                                "evidence": evidence,
                            }
                            for p in merge["parents"]
                        ],
                    },
                )
                return {"kind": "merge", "child": model_id, **merge, "tier": tier}
    # Effectively tied candidates: prefer a foundation reference, then the earliest model.
    best_sim = float(rows[0]["sim"])
    tied = [r for r in rows if best_sim - float(r["sim"]) <= TIE_SIM]
    refs = _references_among(graph, [str(r["parent"]) for r in tied])
    tied.sort(key=lambda r: (str(r["parent"]) not in refs, str(r.get("created_at") or "")))
    top = tied[0]
    sim = float(top["sim"])
    tier = 1 if sim >= settings.dna_derived_min else 0
    evidence = f"weights cosine {sim:.4f} over o_proj+down_proj, 2x{settings.dna_per_tensor} values"
    written = as_rows(
        db.query(
            graph,
            W3,
            {
                "child": model_id,
                "parent": str(top["parent"]),
                "sim": round(sim, 6),
                "tier": tier,
                "evidence": evidence,
            },
        )
    )
    source = written[0].get("source") if written else None
    return {
        "kind": "corroborated" if source == "declared" else "edge",
        "child": model_id,
        "parent": str(top["parent"]),
        "sim": round(sim, 6),
        "tier": tier,
    }


def run_dna_resolver(graph: str = "hub") -> dict[str, Any]:
    started = time.monotonic()
    report: dict[str, Any] = {
        "graph": graph,
        "edges_created": 0,
        "edges_corroborated": 0,
        "merges_found": 0,
        "no_candidate": 0,
        "results": [],
    }
    for row in as_rows(db.ro_query(graph, W12)):
        model_id = str(row["id"])
        try:
            found = resolve_model(graph, model_id)
        except Exception:
            log.exception("dna resolve failed", extra={"model_id": model_id})
            continue
        if found is None:
            report["no_candidate"] += 1
            continue
        key = {"merge": "merges_found", "corroborated": "edges_corroborated"}.get(
            found["kind"], "edges_created"
        )
        report[key] += 1
        report["results"].append(found)
    report["ms"] = int((time.monotonic() - started) * 1000)
    report["at"] = _now()
    _last.clear()
    _last.update(report)
    return report


def reset_weight_edges(graph: str = "hub") -> int:
    """Remove the inferred weight edges we wrote (declared edges keep their source and tier)."""
    rows = as_rows(db.query(graph, W14))
    return int(rows[0]["removed"]) if rows else 0


CONFLICT_MARGIN = 0.005


def verified_conflicts(graph: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only W5 rows the weights can prove.

    A declared parent we could not fingerprint (gated, 4-bit) proves nothing, so the row is
    dropped. A conflict stands when the declared parent has a different shape, or when the
    child is clearly closer (by CONFLICT_MARGIN) to the weights parent than to the declared one.
    """
    ids = {str(r[k]) for r in rows for k in ("model", "declared_parent", "weights_parent")}
    vectors = _vectors(graph, sorted(ids))
    sigs = {
        str(r["id"]): r.get("sig") for r in as_rows(db.ro_query(graph, W11, {"ids": sorted(ids)}))
    }
    kept: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        child, declared = str(row["model"]), str(row["declared_parent"])
        if child in seen or child not in vectors or declared not in vectors:
            continue
        if sigs.get(declared) != sigs.get(child):
            kept.append(
                {**row, "declared_sim": None, "reason": "declared parent has a different shape"}
            )
            seen.add(child)
            continue
        declared_sim = cosine(vectors[child], vectors[declared])
        if float(row["sim"]) - declared_sim >= CONFLICT_MARGIN:
            kept.append(
                {**row, "declared_sim": round(declared_sim, 6), "reason": "closer to another model"}
            )
            seen.add(child)
    return kept


def last_report() -> dict[str, Any]:
    return dict(_last)


# --- fingerprinting and crawl ---------------------------------------------------


def _client() -> HFClient:
    settings = get_settings()
    return HFClient(token=settings.hf_token, cache=DiskCache(Path("/tmp/modelbrain-hf")))


async def fingerprint_into_graph(
    sampler: Sampler, graph: str, model_id: str, sha: str, *, source_repo: str | None = None
) -> str:
    result = await sampler.fingerprint(source_repo or model_id, "main" if source_repo else sha)
    return write_result(graph, model_id, result)


def crawl_status() -> dict[str, Any]:
    return dict(_crawl)


async def crawl(
    model_ids: list[str],
    *,
    graph: str = "hub",
    ingest: Any = None,
    include_references: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    """Ingest (if needed), fingerprint, then resolve. One failing model never stops the run.

    `ingest` is an async callable taking a model id (the Scout path); tests pass a stub.
    """
    settings = get_settings()
    ensure_index(graph)
    client = _client()
    sampler = Sampler(client, settings.dna_per_tensor)
    _crawl.clear()
    _crawl.update(
        {
            "state": "running",
            "started_at": _now(),
            "done": 0,
            "total": 0,
            "statuses": {},
            "errors": 0,
        }
    )
    try:
        refs = references() if include_references else []
        queue: list[tuple[str, str | None]] = [(r["id"], r["fingerprint_from"]) for r in refs]
        queue += [(mid, None) for mid in model_ids if mid not in {r["id"] for r in refs}]
        _crawl["total"] = len(queue)
        for model_id, source in queue:
            try:
                state = {
                    str(r["id"]): r for r in as_rows(db.ro_query(graph, W13, {"ids": [model_id]}))
                }
                if model_id not in state and ingest is not None:
                    await ingest(model_id)
                    state = {
                        str(r["id"]): r
                        for r in as_rows(db.ro_query(graph, W13, {"ids": [model_id]}))
                    }
                if model_id not in state:
                    _crawl["statuses"]["NOT_INGESTED"] = (
                        _crawl["statuses"].get("NOT_INGESTED", 0) + 1
                    )
                    continue
                row = state[model_id]
                if row.get("status") and not force:
                    status = str(row["status"])
                else:
                    if source and source != model_id:
                        status = await fingerprint_into_graph(
                            sampler,
                            graph,
                            model_id,
                            str(row.get("sha") or "main"),
                            source_repo=source,
                        )
                        if ingest is not None and status == OK:
                            await _ensure_mirror_edge(graph, source, model_id, ingest)
                    else:
                        status = await fingerprint_into_graph(
                            sampler, graph, model_id, str(row.get("sha") or "main")
                        )
                _crawl["statuses"][status] = _crawl["statuses"].get(status, 0) + 1
            except HubUnavailable as exc:
                log.warning(
                    "hub unavailable during crawl; backing off", extra={"model_id": model_id}
                )
                _crawl["errors"] += 1
                await asyncio.sleep(min(exc.retry_after_s, 60))
            except Exception:
                log.exception("crawl step failed", extra={"model_id": model_id})
                _crawl["errors"] += 1
            finally:
                _crawl["done"] += 1
        if include_references:
            _crawl["references_marked"] = mark_references(graph)
            _crawl["mirror_fingerprints"] = inherit_mirror_fingerprints(graph)
        from app.engine.resolver import run_resolver

        hashes = run_resolver(graph)
        _crawl["hash_resolver"] = {k: v for k, v in hashes.items() if k != "edges"}
        _crawl["resolver"] = {k: v for k, v in run_dna_resolver(graph).items() if k != "results"}
        _crawl["state"] = "done"
    except Exception:
        log.exception("crawl failed")
        _crawl["state"] = "failed"
    finally:
        _crawl["finished_at"] = _now()
        await client.aclose()
    return crawl_status()


async def _ensure_mirror_edge(graph: str, mirror: str, official: str, ingest: Any) -> None:
    state = as_rows(db.ro_query(graph, W13, {"ids": [mirror]}))
    if not state:
        try:
            await ingest(mirror)
        except Exception:
            log.warning("mirror ingest failed", extra={"model_id": mirror})
            return
    evidence = f"public mirror of {official} used for weight DNA"
    db.query(
        graph,
        R3,
        {
            "child": mirror,
            "parent": official,
            "relation": "mirror",
            "conf": 0.97,
            "tier": 1,
            "evidence": evidence,
        },
    )


def scout_findings_ids() -> list[str]:
    path = repo_root() / "data" / "dna_scout_findings.json"
    data = json.loads(path.read_text())
    ids: list[str] = []
    for key in ("demo_cases", "confirmed_findings_licence_or_wrong_base", "wrong_base_model_cases"):
        for item in data.get(key, []) or []:
            mid = item.get("id") or item.get("repo") if isinstance(item, dict) else None
            if isinstance(mid, str) and mid not in ids:
                ids.append(mid)
    return ids


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a) * sum(y * y for y in b))
    return dot / norm if norm else 0.0
