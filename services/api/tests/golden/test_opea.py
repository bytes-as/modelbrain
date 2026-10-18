"""G035 and G036: OPEA in Germany is blocked; in the US it is allowed with obligations."""

from uuid import uuid4

import pytest

from app.agents.scout import write_parsed
from app.engine.verdict import verdict_from_graph
from app.graph import db
from app.graph.queries import C1
from app.hf.parse import ParsedModel

OPEA = "OPEA/Llama-3.2V-11B-cot-int4-sym-inc"
XKEV = "Xkev/Llama-3.2V-11B-cot"
META = "meta-llama/Llama-3.2-11B-Vision-Instruct"


def _model(
    model_id: str,
    declared: str,
    key: str,
    *,
    root: bool,
    multimodal: bool,
    parents: list[tuple[str, str]],
) -> ParsedModel:
    return ParsedModel(
        model_id=model_id,
        sha="sha",
        declared_license=declared,
        license_key=key,
        pipeline_tag="image-text-to-text" if multimodal else "text-generation",
        created_at="",
        last_modified="",
        gated=False,
        is_root=root,
        multimodal=multimodal,
        card_has_llama_notice=False,
        has_license_file=True,
        name_starts_with="Llama",
        parents=parents,
    )


def _clause(licence: str, name: str, clause_id: str, effect: str, applies: str, quote: str) -> None:
    db.query(
        graph_name,
        C1,
        {
            "license_key": licence,
            "name": name,
            "url": "https://example.com",
            "id": clause_id,
            "kind": "k",
            "effect": effect,
            "applies_when": applies,
            "check": "",
            "summary": clause_id,
            "quote": quote,
            "locator": "x",
            "source_url": "https://example.com/" + clause_id,
            "source_raw_url": "https://example.com/raw",
            "section": "1",
        },
    )


graph_name = ""


@pytest.fixture
def seeded() -> str:
    global graph_name
    db.connect(tries=5, delay_s=0.5)
    graph_name = "g035_" + uuid4().hex[:8]
    write_parsed(
        graph_name,
        _model(
            OPEA,
            "apache-2.0",
            "apache-2.0",
            root=False,
            multimodal=False,
            parents=[(XKEV, "quantized")],
        ),
        1,
    )
    write_parsed(
        graph_name,
        _model(
            XKEV,
            "apache-2.0",
            "apache-2.0",
            root=False,
            multimodal=True,
            parents=[(META, "finetune")],
        ),
        1,
    )
    write_parsed(
        graph_name, _model(META, "llama3.2", "llama3_2", root=True, multimodal=True, parents=[]), 1
    )
    _clause(
        "llama3_2",
        "Llama 3.2",
        "llama3_2.geo_eu_multimodal",
        "BLOCK",
        '{"all":[{"hq_in":"EU"},{"ancestor_multimodal":true},{"not":{"end_user_only":true}}]}',
        "rights are not granted in the European Union",
    )
    _clause(
        "llama3_2",
        "Llama 3.2",
        "llama3_2.built_with_notice",
        "OBLIGATION",
        '{"always": true}',
        "Built with Llama",
    )
    _clause(
        "llama3_2",
        "Llama 3.2",
        "llama3_2.aup",
        "OBLIGATION",
        '{"always": true}',
        "Acceptable Use Policy",
    )
    yield graph_name
    db.delete_graph(graph_name)


def test_opea_de_is_blocked(seeded: str) -> None:
    decided = verdict_from_graph(
        OPEA,
        {
            "hq_country": "DE",
            "markets": ["DE"],
            "commercial": True,
            "mau": 0,
            "distributes_weights": False,
            "end_user_only": False,
        },
        graph=seeded,
    )
    assert decided["verdict"] == "BLOCKED"
    assert decided["declared_differs"] is True
    assert any(hit["clause_id"] == "llama3_2.geo_eu_multimodal" for hit in decided["blocking"])
    assert decided["blocking"][0]["path"][0] == OPEA
    assert META in decided["blocking"][0]["path"]


def test_opea_us_has_obligations(seeded: str) -> None:
    decided = verdict_from_graph(
        OPEA,
        {
            "hq_country": "US",
            "markets": ["US"],
            "commercial": True,
            "mau": 2000000,
            "distributes_weights": False,
            "end_user_only": False,
        },
        graph=seeded,
    )
    assert decided["verdict"] == "ALLOWED_WITH_OBLIGATIONS"
    ids = {hit["clause_id"] for hit in decided["obligations"]}
    assert "llama3_2.built_with_notice" in ids
    assert "llama3_2.aup" in ids
    assert decided["disclaimer"] == "Automated screening, not legal advice."
