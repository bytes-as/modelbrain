"""G074: proof_path returns a path or no_path."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.agents.scout import write_parsed
from app.graph import db
from app.hf.parse import ParsedModel
from app.main import app


def _model(model_id: str, *, root: bool, parents: list[tuple[str, str]]) -> ParsedModel:
    return ParsedModel(
        model_id=model_id,
        sha="sha",
        declared_license="apache-2.0",
        license_key="apache-2.0",
        pipeline_tag="text-generation",
        created_at="",
        last_modified="",
        gated=False,
        is_root=root,
        multimodal=False,
        card_has_llama_notice=False,
        has_license_file=True,
        name_starts_with="X",
        parents=parents,
    )


def test_proof_path_endpoint() -> None:
    db.connect(tries=5, delay_s=0.5)
    child = "demo/proof-child"
    root = "demo/proof-root"
    write_parsed("hub", _model(root, root=True, parents=[]), 1)
    write_parsed("hub", _model(child, root=False, parents=[(root, "finetune")]), 1)
    client = TestClient(app)
    ok = client.get("/api/models/demo/proof-child/proof-path", params={"root_id": root})
    assert ok.status_code == 200
    body = ok.json()
    assert body["no_path"] is False
    assert root in body["path"]
    missing = client.get(
        "/api/models/demo/proof-child/proof-path",
        params={"root_id": "demo/other-root"},
    )
    assert missing.status_code == 200
    assert missing.json()["no_path"] is True
