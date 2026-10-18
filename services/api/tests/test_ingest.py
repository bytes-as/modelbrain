"""G023 and G024: Scout writes the OPEA ancestry and records skipped files."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.agents.scout import ingest
from app.graph import db
from app.hf.parse import load_normalise

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "hf"


def _repo() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "data" / "clauses.seed.json").is_file():
            return parent
    raise FileNotFoundError("data")


REPO = _repo()
TABLE = load_normalise(json.loads((REPO / "data" / "clauses.seed.json").read_text()))
ROOTS = set(json.loads((REPO / "data" / "roots.json").read_text())["orgs"])


class FixtureHub:
    def __init__(self, files: dict[tuple[str, str], tuple[int, str | None]] | None = None) -> None:
        names = {
            "OPEA/Llama-3.2V-11B-cot-int4-sym-inc": "opea.json",
            "Xkev/Llama-3.2V-11B-cot": "xkev.json",
            "meta-llama/Llama-3.2-11B-Vision-Instruct": "meta-vision.json",
        }
        self.models = {
            model_id: json.loads((FIXTURES / name).read_text()) for model_id, name in names.items()
        }
        self.files = files or {}

    async def model(self, model_id: str) -> tuple[int, dict | None]:
        payload = self.models.get(model_id)
        if payload is None:
            return 404, None
        return 200, payload

    async def file_at_sha(self, model_id: str, _sha: str, filename: str) -> tuple[int, str | None]:
        return self.files.get((model_id, filename), (404, None))

    async def children(self, _model_id: str, _relation: str, _limit: int) -> list[str]:
        return []


@pytest.fixture
def graph_name() -> str:
    db.connect(tries=5, delay_s=0.5)
    name = f"g023_{uuid4().hex[:8]}"
    yield name
    try:
        db.delete_graph(name)
    except Exception:
        pass


@pytest.mark.asyncio
async def test_opea_ancestry_writes_two_tier2_edges(graph_name: str) -> None:
    result = await ingest(
        "OPEA/Llama-3.2V-11B-cot-int4-sym-inc",
        FixtureHub(),
        table=TABLE,
        roots=ROOTS,
        graph=graph_name,
    )
    assert result.nodes == 3
    rows = db.ro_query(
        graph_name,
        "MATCH (c:Model)-[e:DERIVED_FROM]->(p:Model) RETURN c.id, e.tier, p.id ORDER BY c.id",
    ).result_set
    assert rows == [
        ["OPEA/Llama-3.2V-11B-cot-int4-sym-inc", 2, "Xkev/Llama-3.2V-11B-cot"],
        ["Xkev/Llama-3.2V-11B-cot", 2, "meta-llama/Llama-3.2-11B-Vision-Instruct"],
    ]


@pytest.mark.asyncio
async def test_gated_readme_is_skipped(graph_name: str) -> None:
    hub = FixtureHub(
        files={
            ("meta-llama/Llama-3.2-11B-Vision-Instruct", "README.md"): (403, None),
            ("meta-llama/Llama-3.2-11B-Vision-Instruct", "config.json"): (401, None),
        }
    )
    result = await ingest(
        "meta-llama/Llama-3.2-11B-Vision-Instruct",
        hub,
        table=TABLE,
        roots=ROOTS,
        graph=graph_name,
    )
    assert any(reason.startswith("README skipped: 403") for reason in result.incomplete_reasons)
    assert any(reason.startswith("config skipped: 401") for reason in result.incomplete_reasons)


@pytest.mark.asyncio
async def test_children_ingest_writes_one_level(graph_name: str) -> None:
    root_id = "meta-llama/Llama-3.2-11B-Vision-Instruct"
    child_ids = [f"demo/child-{index:02d}" for index in range(25)]
    base = json.loads((FIXTURES / "meta-vision.json").read_text())

    class ChildHub(FixtureHub):
        def __init__(self) -> None:
            super().__init__()
            self.models[root_id] = base
            for child_id in child_ids:
                payload = dict(base)
                payload["id"] = child_id
                payload["modelId"] = child_id
                payload["cardData"] = {}
                payload["tags"] = []
                self.models[child_id] = payload

        async def children(self, model_id: str, relation: str, limit: int) -> list[str]:
            if model_id == root_id and relation == "finetune":
                return child_ids[:limit]
            return []

    result = await ingest(
        root_id,
        ChildHub(),
        table=TABLE,
        roots=ROOTS,
        graph=graph_name,
        children=True,
    )
    assert result.nodes >= 26
    rows = db.ro_query(
        graph_name,
        "MATCH (:Model {id: $root})<-[:DERIVED_FROM]-(c:Model) RETURN count(c)",
        {"root": root_id},
    ).result_set
    assert int(rows[0][0]) >= 25
