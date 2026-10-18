"""G141, G142, G150, G151: fingerprint writes, weight resolver, merge fit and exposure on FalkorDB."""

from __future__ import annotations

import random
from uuid import uuid4

import pytest

from app.engine import dna
from app.graph import db
from app.graph.queries import W4, W5, W6, W8, W10
from app.graph.rows import as_rows
from app.hf.dna import ERROR, GATED, OK, DnaResult

D = 1024
SIG = "h2048|L16|i8192"


def _vec(rng: random.Random) -> list[float]:
    return [rng.uniform(-1, 1) for _ in range(D)]


def _near(rng: random.Random, v: list[float], noise: float) -> list[float]:
    return [x + rng.gauss(0, noise) for x in v]


@pytest.fixture()
def graph():
    db.connect(tries=5, delay_s=0.5)
    name = f"dna_{uuid4().hex[:8]}"
    dna.ensure_index(name)
    yield name
    db.delete_graph(name)


def _model(graph: str, model_id: str, created: str, **props: object) -> None:
    db.query(
        graph,
        "CREATE (:Model {id: $id, created_at: $created, declared_license: $lic, is_root: $root})",
        {
            "id": model_id,
            "created": created,
            "lic": props.get("lic"),
            "root": bool(props.get("root")),
        },
    )


def _fp(graph: str, model_id: str, vector: list[float], sig: str = SIG) -> str:
    return dna.write_result(graph, model_id, DnaResult(OK, vector=vector, sig=sig))


def test_writer_refuses_bad_vectors(graph: str) -> None:
    _model(graph, "a/ok", "2025-01-01")
    _model(graph, "a/short", "2025-01-01")
    _model(graph, "a/nan", "2025-01-01")
    _model(graph, "a/gated", "2025-01-01")
    rng = random.Random(1)
    assert _fp(graph, "a/ok", _vec(rng)) == OK
    assert _fp(graph, "a/short", [1.0, 2.0]) == ERROR
    assert _fp(graph, "a/nan", [float("nan")] * D) == ERROR
    assert dna.write_result(graph, "a/gated", DnaResult(GATED, reason="401")) == GATED
    counts = {r["status"]: r["models"] for r in as_rows(db.ro_query(graph, W6))}
    assert counts == {"OK": 1, "ERROR": 2, "GATED": 1}


def test_resolver_scenario(graph: str) -> None:
    rng = random.Random(7)
    base, other, l31 = _vec(rng), _vec(rng), None
    l31 = _near(rng, base, 0.15)  # a second foundation close to the first (like Llama 3 vs 3.1)
    _model(graph, "meta/base", "2024-04-18", lic="llama3_2", root=True)
    _model(graph, "meta/base31", "2024-07-23", lic="llama3_1", root=True)
    _model(graph, "x/hidden", "2025-01-01", lic="apache-2.0")
    _model(graph, "y/declared", "2025-02-01", lic="llama3_2")
    _model(graph, "z/unrelated", "2025-03-01", lic="mit")
    _model(graph, "q/otherarch", "2025-03-02")
    _model(graph, "w/conflict", "2025-04-01")
    _model(graph, "v/claimed", "2024-01-01", root=True)
    _model(graph, "org/distill", "2025-01-20", root=True)  # org repo, not a reference
    db.query(
        graph,
        "MATCH (y:Model {id:'y/declared'}),(b:Model {id:'meta/base'}) "
        "CREATE (y)-[:DERIVED_FROM {relation:'finetune', source:'declared', tier:2, conf:1.0}]->(b)",
    )
    db.query(
        graph,
        "MATCH (w:Model {id:'w/conflict'}),(v:Model {id:'v/claimed'}) "
        "CREATE (w)-[:DERIVED_FROM {relation:'finetune', source:'declared', tier:2, conf:1.0}]->(v)",
    )
    for mid, vec, sig in [
        ("meta/base", base, SIG),
        ("meta/base31", l31, SIG),
        ("x/hidden", _near(rng, base, 0.05), SIG),
        ("y/declared", _near(rng, base, 0.08), SIG),
        ("z/unrelated", other, SIG),
        ("q/otherarch", _near(rng, base, 0.01), "h1536|L28|i8960"),
        ("w/conflict", _near(rng, base, 0.06), SIG),
        ("v/claimed", _vec(rng), SIG),
        ("org/distill", _near(rng, l31, 0.05), SIG),
    ]:
        assert _fp(graph, mid, vec, sig) == OK
    db.query(graph, W10, {"ids": ["meta/base", "meta/base31"]})

    report = dna.run_dna_resolver(graph)
    by_child = {r["child"]: r for r in report["results"]}

    assert "meta/base31" not in by_child  # references never get weight edges
    assert by_child["x/hidden"]["parent"] == "meta/base"
    assert by_child["x/hidden"]["tier"] == 1
    assert by_child["y/declared"]["kind"] == "corroborated"
    assert by_child["org/distill"]["parent"] == "meta/base31"  # non-reference root still resolves
    assert "z/unrelated" not in by_child and "q/otherarch" not in by_child

    declared = as_rows(
        db.ro_query(
            graph,
            "MATCH (:Model {id:'y/declared'})-[e:DERIVED_FROM]->(:Model {id:'meta/base'}) "
            "RETURN e.source AS source, e.tier AS tier, e.weights_sim AS sim",
        )
    )
    assert (
        declared[0]["source"] == "declared"
        and declared[0]["tier"] == 2
        and declared[0]["sim"] > 0.9
    )

    hidden = {r["model"]: r for r in as_rows(db.ro_query(graph, W4, {"limit": 20}))}
    assert hidden["x/hidden"]["root"] == "meta/base"
    assert hidden["x/hidden"]["root_license"] == "llama3_2"
    assert "y/declared" not in hidden and "w/conflict" not in hidden

    conflicts = as_rows(db.ro_query(graph, W5, {"limit": 20}))
    assert [r["model"] for r in conflicts] == ["w/conflict"]

    strict = as_rows(
        db.ro_query(
            graph,
            "MATCH (:Model {id:'x/hidden'})-[e:DERIVED_FROM]->() WHERE e.tier >= 2 RETURN count(e) AS n",
        )
    )
    assert strict[0]["n"] == 0


def test_merge_fit_and_exposure(graph: str) -> None:
    rng = random.Random(11)
    p, q = _vec(rng), _vec(rng)
    child = [0.31 * a + 0.69 * b for a, b in zip(p, q, strict=True)]
    _model(graph, "mi/p", "2024-01-30", lic="other")
    _model(graph, "meta/q", "2024-04-18", lic="llama3", root=True)
    _model(graph, "x/merged", "2024-09-01", lic="apache-2.0")
    for mid, vec in [("mi/p", p), ("meta/q", q), ("x/merged", child)]:
        assert _fp(graph, mid, vec) == OK
    db.query(graph, W10, {"ids": ["meta/q"]})
    found = dna.resolve_model(graph, "x/merged")
    assert found and found["kind"] == "merge"
    shares = {pp["id"]: pp["share"] for pp in found["parents"]}
    assert abs(shares["mi/p"] - 0.31) < 0.01 and abs(shares["meta/q"] - 0.69) < 0.01
    exposure = {
        r["root"]: r["exposure"]
        for r in as_rows(db.ro_query(graph, W8, {"id": "x/merged", "min_tier": 1}))
    }
    assert abs(exposure["meta/q"] - 0.69) < 0.01
    assert abs(exposure["mi/p"] - 0.31) < 0.01


def test_plain_finetune_is_not_a_merge() -> None:
    rng = random.Random(3)
    base, sibling = _vec(rng), _vec(rng)
    child = _near(rng, base, 0.05)
    assert dna.best_merge(child, {"base": base, "sibling": sibling}, 512) is None


def test_wrong_close_pair_loses_to_the_true_pair() -> None:
    rng = random.Random(5)
    a, b = _vec(rng), _vec(rng)
    a2 = _near(rng, a, 0.15)  # near-duplicate of a
    child = [0.6 * x + 0.4 * y for x, y in zip(a, b, strict=True)]
    best = dna.best_merge(child, {"a": a, "a2": a2, "b": b}, 512)
    assert best is not None
    assert {p["id"] for p in best["parents"]} == {"a", "b"}


def test_trace_weights_is_an_mcp_tool() -> None:
    import asyncio

    from app.mcp_server import mcp

    names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert "trace_weights" in names


def test_verdict_paths_carry_weight_evidence(graph: str) -> None:
    from app.engine.verdict import verdict_from_graph

    rng = random.Random(21)
    base = _vec(rng)
    _model(graph, "meta/base", "2024-04-18", lic="llama3_2", root=True)
    _model(graph, "x/hidden", "2025-01-01", lic="apache-2.0")
    _fp(graph, "meta/base", base)
    _fp(graph, "x/hidden", _near(rng, base, 0.05))
    db.query(graph, W10, {"ids": ["meta/base"]})
    dna.run_dna_resolver(graph)
    context = {
        "hq_country": "US",
        "markets": ["US"],
        "commercial": True,
        "mau": 0,
        "distributes_weights": False,
        "end_user_only": False,
    }
    decided = verdict_from_graph("x/hidden", context, graph=graph, min_tier=1)
    hop = [p for p in decided["paths"] if len(p["path"]) == 2]
    assert hop and hop[0]["methods"] == ["weights"]
    assert hop[0]["weights_sims"][0] > 0.9


def test_gated_official_inherits_mirror_config_fingerprint(graph: str) -> None:
    db.query(
        graph,
        "CREATE (o:Model {id:'meta-llama/Llama-3.2-1B'}), (m:Model {id:'unsloth/Llama-3.2-1B'}),"
        " (f:Fingerprint {key:'config_fp:abc', kind:'config_fp', value:'abc'}), (m)-[:HAS_FP]->(f)",
    )
    assert dna.inherit_mirror_fingerprints(graph) >= 1
    rows = as_rows(
        db.ro_query(
            graph,
            "MATCH (:Model {id:'meta-llama/Llama-3.2-1B'})-[:HAS_FP]->(f:Fingerprint) RETURN f.kind AS k",
        )
    )
    assert rows == [{"k": "config_fp"}]
