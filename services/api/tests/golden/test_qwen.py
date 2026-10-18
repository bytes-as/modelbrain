"""G038: Qwen2.5-7B-Instruct is never blocked in Germany."""

from uuid import uuid4

import pytest

from app.engine.verdict import verdict_from_graph
from app.graph import db
from tests.golden.helpers import EU_COMMERCIAL, clause, model, write

QWEN = "Qwen/Qwen2.5-7B-Instruct"


@pytest.fixture
def graph_name() -> str:
    db.connect(tries=5, delay_s=0.5)
    name = f"g038_{uuid4().hex[:8]}"
    write(name, model(QWEN, "apache-2.0", "apache-2.0", root=True, name_starts_with="Qwen"))
    clause(
        name,
        "apache-2.0",
        "Apache",
        "apache.give_license",
        "OBLIGATION",
        '{"distributes_weights": true}',
        "give recipients a copy of the licence",
        check='{"license_file_present": true}',
    )
    yield name
    db.delete_graph(name)


def test_qwen_de_not_blocked(graph_name: str) -> None:
    decided = verdict_from_graph(QWEN, EU_COMMERCIAL, graph=graph_name)
    assert decided["verdict"] != "BLOCKED"


def test_qwen_obligations_when_redistributing_weights(graph_name: str) -> None:
    ctx = {**EU_COMMERCIAL, "distributes_weights": True}
    decided = verdict_from_graph(QWEN, ctx, graph=graph_name)
    assert decided["verdict"] in ("ALLOWED", "ALLOWED_WITH_OBLIGATIONS")
    if decided["verdict"] == "ALLOWED_WITH_OBLIGATIONS":
        assert any(hit["clause_id"] == "apache.give_license" for hit in decided["obligations"])
