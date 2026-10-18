"""G051-G054: fingerprints, WCC edges, strict vs default for parentless models."""

from __future__ import annotations

from uuid import uuid4

from app.agents.scout import write_parsed
from app.engine.resolver import run_resolver
from app.engine.verdict import verdict_from_graph
from app.graph import db
from app.graph.rows import as_rows
from app.hf.parse import Fingerprint, ParsedModel

META = "meta-llama/Llama-3.2-1B"
SIC = "SicariusSicariiStuff/Llama-3.2-1B_Base_FP8"
ALP = "alpindale/Llama-3.2-1B"
SHA = "68a2e4be76fa7094aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def _model(model_id: str, *, root: bool, parents=(), fps=()) -> ParsedModel:
    return ParsedModel(
        model_id=model_id,
        sha="sha",
        declared_license="llama3.2",
        license_key="llama3_2",
        pipeline_tag="text-generation",
        created_at="2024-01-01",
        last_modified="2024-01-01",
        gated=False,
        is_root=root,
        multimodal=False,
        card_has_llama_notice=False,
        has_license_file=True,
        name_starts_with="Llama",
        parents=list(parents),
        fingerprints=list(fps),
    )


def test_resolver_infers_parent_and_strict_cannot_determine() -> None:
    db.connect(tries=5, delay_s=0.5)
    graph = f"g053_{uuid4().hex[:8]}"
    try:
        fps = [
            Fingerprint(key=f"weights_sha256:{SHA}", kind="weights_sha256", value=SHA),
            Fingerprint(key="tokenizer_sha:tok", kind="tokenizer_sha", value="tok"),
            Fingerprint(key="config_fp:cfg", kind="config_fp", value="cfg"),
        ]
        write_parsed(graph, _model(META, root=True, fps=fps), 1)
        write_parsed(graph, _model(SIC, root=False, parents=[], fps=fps), 1)
        write_parsed(
            graph,
            _model(ALP, root=False, parents=[], fps=[fps[0]]),
            1,
        )
        report = run_resolver(graph)
        assert report["mirror"] + report["inferred_t1"] >= 1
        edges = as_rows(
            db.ro_query(
                graph,
                "MATCH (c:Model)-[e:DERIVED_FROM]->(p:Model) "
                "RETURN c.id AS child, p.id AS parent, e.relation AS relation, e.tier AS tier, e.source AS source",
            )
        )
        sic_edges = [e for e in edges if e["child"] == SIC]
        assert sic_edges
        assert sic_edges[0]["parent"] == META
        assert sic_edges[0]["source"] == "inferred"
        assert int(sic_edges[0]["tier"]) >= 1
        ctx = {
            "hq_country": "US",
            "markets": ["US"],
            "commercial": True,
            "mau": 0,
            "distributes_weights": False,
            "end_user_only": False,
        }
        strict = verdict_from_graph(SIC, ctx, graph=graph, min_tier=2)
        assert strict["verdict"] == "CANNOT_DETERMINE"
        default = verdict_from_graph(SIC, ctx, graph=graph, min_tier=1)
        assert default["verdict"] != "CANNOT_DETERMINE" or default["lineage_complete"]
    finally:
        try:
            db.delete_graph(graph)
        except Exception:
            pass


def test_declared_differs_compares_licence_keys_over_trusted_edges() -> None:
    from app.engine.resolver import set_declared_differs

    db.connect(tries=5, delay_s=0.5)
    graph = f"g059_{uuid4().hex[:8]}"
    try:
        db.query(
            graph,
            "CREATE (l31:License {key:'llama3_1'}), (ap:License {key:'apache-2.0'}),"
            " (base:Model {id:'meta/base', declared_license:'llama3.1'})-[:DECLARES]->(l31),"
            " (inst:Model {id:'meta/inst', declared_license:'llama3.1'})-[:DECLARES]->(l31),"
            " (relabel:Model {id:'x/relabel', declared_license:'apache-2.0'})-[:DECLARES]->(ap),"
            " (weak:Model {id:'y/weak', declared_license:'apache-2.0'})-[:DECLARES]->(ap),"
            " (inst)-[:DERIVED_FROM {tier:2}]->(base),"
            " (relabel)-[:DERIVED_FROM {tier:1}]->(inst),"
            " (weak)-[:DERIVED_FROM {tier:0}]->(base),"
            " (l33:License {key:'llama3_3'}),"
            " (newer:Model {id:'meta/newer', declared_license:'llama3.3'})-[:DECLARES]->(l33),"
            " (newer)-[:DERIVED_FROM {tier:2}]->(base)",
        )
        assert set_declared_differs(graph) == 1
        flags = dict(
            db.ro_query(graph, "MATCH (m:Model) RETURN m.id, m.declared_differs").result_set
        )
        assert flags == {
            "meta/base": False,
            "meta/inst": False,
            "x/relabel": True,
            "y/weak": False,
            "meta/newer": False,  # a newer licence in the same family is not a relabel
        }
    finally:
        db.delete_graph(graph)
