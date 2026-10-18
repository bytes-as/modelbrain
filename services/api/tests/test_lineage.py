"""G028: lineage endpoint returns distinct edges from Q3."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.scout import ingest
from app.graph import db
from app.hf.parse import load_normalise
from app.main import app

FIX = Path(__file__).resolve().parent / "fixtures" / "hf"
def _repo() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "data" / "clauses.seed.json").is_file():
            return parent
    raise FileNotFoundError("data")


REPO_ROOT = _repo()


class FixtureHub:
    def __init__(self) -> None:
        names = {
            "OPEA/Llama-3.2V-11B-cot-int4-sym-inc": "opea.json",
            "Xkev/Llama-3.2V-11B-cot": "xkev.json",
            "meta-llama/Llama-3.2-11B-Vision-Instruct": "meta-vision.json",
        }
        self.models = {
            model_id: json.loads((FIX / name).read_text()) for model_id, name in names.items()
        }

    async def model(self, model_id: str):
        payload = self.models.get(model_id)
        return (404, None) if payload is None else (200, payload)

    async def file_at_sha(self, _model_id: str, _sha: str, _filename: str):
        return 404, None

    async def children(self, _model_id: str, _relation: str, _limit: int):
        return []


@pytest.fixture
def graph_name() -> str:
    db.connect(tries=5, delay_s=0.5)
    name = f"g028_{uuid4().hex[:8]}"
    yield name
    try:
        db.delete_graph(name)
    except Exception:
        pass


@pytest.mark.asyncio
async def test_lineage_distinct_edges(graph_name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    table = load_normalise(
        json.loads((REPO_ROOT / "data" / "clauses.seed.json").read_text())
    )
    roots = set(json.loads((REPO_ROOT / "data" / "roots.json").read_text())["orgs"])
    await ingest(
        "OPEA/Llama-3.2V-11B-cot-int4-sym-inc",
        FixtureHub(),
        table=table,
        roots=roots,
        graph=graph_name,
    )
    monkeypatch.setattr("app.routes.models.ro_query", lambda graph, q, params: db.ro_query(graph_name, q, params))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/models/OPEA/Llama-3.2V-11B-cot-int4-sym-inc/lineage",
            params={"min_tier": 0},
        )
    assert response.status_code == 200
    payload = response.json()
    edge_keys = {(e["child"], e["parent"]) for e in payload["edges"]}
    assert len(edge_keys) == len(payload["edges"])
    assert len(payload["edges"]) >= 2
