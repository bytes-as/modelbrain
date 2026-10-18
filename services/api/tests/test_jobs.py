"""G025: ingest jobs and SSE events."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.agents import scout as scout_mod
from app.graph import db
from app.hf.parse import load_normalise
from app.jobs.registry import jobs
from app.main import app

FIX = Path(__file__).resolve().parent / "fixtures" / "hf"


def _repo() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "data" / "clauses.seed.json").is_file():
            return parent
    raise FileNotFoundError("data")


REPO_ROOT = _repo()
TABLE = load_normalise(json.loads((REPO_ROOT / "data" / "clauses.seed.json").read_text()))
ROOTS = set(json.loads((REPO_ROOT / "data" / "roots.json").read_text())["orgs"])


def _opea_hub():
    names = {
        "OPEA/Llama-3.2V-11B-cot-int4-sym-inc": "opea.json",
        "Xkev/Llama-3.2V-11B-cot": "xkev.json",
        "meta-llama/Llama-3.2-11B-Vision-Instruct": "meta-vision.json",
    }
    models = {model_id: json.loads((FIX / name).read_text()) for model_id, name in names.items()}

    class Hub:
        async def model(self, model_id: str):
            payload = models.get(model_id)
            return (404, None) if payload is None else (200, payload)

        async def file_at_sha(self, _model_id: str, _sha: str, _filename: str):
            return 404, None

        async def children(self, _model_id: str, _relation: str, _limit: int):
            return []

    return Hub()


@pytest.fixture
def graph_name() -> str:
    db.connect(tries=5, delay_s=0.5)
    name = f"g025_{uuid4().hex[:8]}"
    yield name
    try:
        db.delete_graph(name)
    except Exception:
        pass


@pytest.mark.asyncio
async def test_ingest_job_emits_started_node_done(graph_name: str) -> None:
    hub = _opea_hub()

    async def run(job_id: str, model_id: str, *, children: bool = False) -> None:
        registry = jobs()

        def emit(event: dict[str, object]) -> None:
            registry.emit(job_id, event)

        await scout_mod.ingest(
            model_id,
            hub,
            table=TABLE,
            roots=ROOTS,
            graph=graph_name,
            emit=emit,
        )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.jobs.runner._run_job", side_effect=run):
            response = await client.post(
                "/api/ingest",
                json={"model_id": "OPEA/Llama-3.2V-11B-cot-int4-sym-inc"},
            )
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        for _ in range(100):
            status = await client.get(f"/api/jobs/{job_id}")
            if status.json()["status"] != "running":
                break
            await asyncio.sleep(0.02)
        status = await client.get(f"/api/jobs/{job_id}")
        assert status.json()["status"] == "done"
        assert status.json()["nodes"] >= 3
        kinds: list[str] = []
        async with client.stream("GET", f"/api/jobs/{job_id}/events") as stream:
            async for line in stream.aiter_lines():
                if line.startswith("data: "):
                    kinds.append(json.loads(line[6:])["type"])
        assert kinds[0] == "started"
        assert "node" in kinds
        assert kinds[-1] == "done"
