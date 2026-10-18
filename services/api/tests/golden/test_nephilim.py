"""G031 and G037: merge DAG licences and cc-by-nc commercial block."""

from uuid import uuid4

import pytest

from app.engine.verdict import verdict_from_graph
from app.graph import db
from app.graph.queries import Q1
from app.graph.rows import as_rows
from tests.golden.helpers import EU_COMMERCIAL, clause, model, write

NEPH = "grimjim/llama-3-Nephilim-v1-8B"
P1 = "WhiteRabbitNeo/Llama-3-WhiteRabbitNeo-8B-v2.0"
P2 = "mlabonne/NeuralDaredevil-8B-abliterated"
R1 = "meta-llama/Meta-Llama-3-8B"


@pytest.fixture
def graph_name() -> str:
    db.connect(tries=5, delay_s=0.5)
    name = f"g031_{uuid4().hex[:8]}"
    write(
        name,
        model(
            NEPH,
            "cc-by-nc-4.0",
            "cc-by-nc-4.0",
            root=False,
            parents=[(P1, "merge"), (P2, "merge")],
            name_starts_with="llama",
        ),
    )
    write(name, model(P1, "llama3", "llama3_2", root=False, parents=[(R1, "finetune")]))
    write(name, model(R1, "llama3.2", "llama3_2", root=True))
    write(name, model(P2, "apache-2.0", "apache-2.0", root=True))
    clause(
        name,
        "cc-by-nc-4.0",
        "CC BY-NC",
        "ccbync.noncommercial",
        "BLOCK",
        '{"commercial": true}',
        "non-commercial purposes only",
    )
    clause(
        name,
        "cc-by-nc-4.0",
        "CC BY-NC",
        "ccbync.attribution",
        "OBLIGATION",
        '{"always": true}',
        "give appropriate credit",
    )
    yield name
    db.delete_graph(name)


def test_q1_returns_every_licence_on_the_merge_dag(graph_name: str) -> None:
    rows = as_rows(db.ro_query(graph_name, Q1, {"model_id": NEPH, "min_tier": 1}))
    licences = {str(row.get("license") or "") for row in rows if row.get("license")}
    assert "cc-by-nc-4.0" in licences
    assert "llama3_2" in licences
    assert "apache-2.0" in licences
    assert len(rows) >= 3


def test_nephilim_commercial_is_blocked(graph_name: str) -> None:
    decided = verdict_from_graph(NEPH, EU_COMMERCIAL, graph=graph_name)
    assert decided["verdict"] == "BLOCKED"
    assert any(hit["clause_id"] == "ccbync.noncommercial" for hit in decided["blocking"])


def test_nephilim_noncommercial_has_obligations(graph_name: str) -> None:
    ctx = {**EU_COMMERCIAL, "commercial": False}
    decided = verdict_from_graph(NEPH, ctx, graph=graph_name)
    assert decided["verdict"] == "ALLOWED_WITH_OBLIGATIONS"
    assert any(hit["clause_id"] == "ccbync.attribution" for hit in decided["obligations"])
