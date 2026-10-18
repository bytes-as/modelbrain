"""Autocomplete over ingested hub models (X32)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.graph import db
from app.main import app

IDS = ("zzsearch/Alpha-Model-1B", "zzsearch/beta-alpha-7B", "zzsearch/NotIngested-1B")


@pytest.fixture(autouse=True)
def _models():
    db.connect(tries=5, delay_s=0.5)
    for model_id in IDS:
        sha = None if "NotIngested" in model_id else "abc"
        db.query("hub", "MERGE (m:Model {id: $id}) SET m.sha = $sha", {"id": model_id, "sha": sha})
    yield
    db.query("hub", "MATCH (m:Model) WHERE m.id IN $ids DETACH DELETE m", {"ids": list(IDS)})


def test_search_ranks_prefix_matches_first_and_skips_placeholders() -> None:
    client = TestClient(app)
    response = client.get("/api/models/search", params={"q": "ALPHA"})
    assert response.status_code == 200, response.text
    ids = [row["id"] for row in response.json() if row["id"].startswith("zzsearch/")]
    assert ids == ["zzsearch/Alpha-Model-1B", "zzsearch/beta-alpha-7B"]


def test_search_rejects_odd_input() -> None:
    client = TestClient(app)
    assert client.get("/api/models/search", params={"q": "a"}).status_code == 422
    assert client.get("/api/models/search", params={"q": "llama'}) RETURN 1"}).status_code == 422
