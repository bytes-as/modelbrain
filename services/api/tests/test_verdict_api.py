"""G040, G043, G046: POST /api/verdict returns a typed verdict from the hub."""

from fastapi.testclient import TestClient

from app.agents.scout import write_parsed
from app.graph import db
from app.graph.queries import C1
from app.hf.parse import ParsedModel
from app.main import app

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


def _seed() -> None:
    db.connect(tries=5, delay_s=0.5)
    write_parsed(
        "hub",
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
        "hub",
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
        "hub",
        _model(META, "llama3.2", "llama3_2", root=True, multimodal=True, parents=[]),
        1,
    )
    for clause_id, effect, applies, quote in (
        (
            "llama3_2.geo_eu_multimodal",
            "BLOCK",
            '{"all":[{"hq_in":"EU"},{"ancestor_multimodal":true},{"not":{"end_user_only":true}}]}',
            "rights are not granted in the European Union",
        ),
        ("llama3_2.built_with_notice", "OBLIGATION", '{"always": true}', "Built with Llama"),
        ("llama3_2.aup", "OBLIGATION", '{"always": true}', "Acceptable Use Policy"),
    ):
        db.query(
            "hub",
            C1,
            {
                "license_key": "llama3_2",
                "name": "Llama 3.2",
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


def test_verdict_endpoint_blocks_opea_in_germany() -> None:
    _seed()
    client = TestClient(app)
    response = client.post(
        "/api/verdict",
        json={
            "model_id": OPEA,
            "context": {"hq_country": "de", "commercial": True},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verdict"] == "BLOCKED"
    assert body["declared_differs"] is True
    assert body["disclaimer"] == "Automated screening, not legal advice."
    assert "MATCH" in body["cypher"]["q1"]
    assert "MATCH" in body["cypher"]["q2"]
    assert isinstance(body["computed_ms"], int)
    assert body["explanation_source"] == "template"
    assert response.headers["x-request-id"]


def test_verdict_rejects_a_bad_model_id() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/verdict",
        json={"model_id": "not a model", "context": {"hq_country": "DE"}},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"
